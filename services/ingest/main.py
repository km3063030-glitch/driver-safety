import json
import signal
import time
from collections import Counter
from datetime import datetime, timezone

import psycopg
import redis
from confluent_kafka import Consumer, Producer
from psycopg.types.json import Jsonb

from services.common import config
from services.common.events import HARSH, validate
from services.ingest.rules import HarshBurstRule


def write_alerts(conn, producer, alerts):
    rows = []
    for event, count in alerts:
        severity = "HIGH" if count >= 2 * config.ALERT_THRESHOLD else "MEDIUM"
        details = {
            "count": count,
            "window_s": config.ALERT_WINDOW_S,
            "last_event": event["evt"],
            "lat": event["lat"],
            "lon": event["lon"],
        }
        raised = datetime.fromtimestamp(event["_t"], timezone.utc)
        rows.append((event["vin"], "HARSH_BURST", severity, raised, Jsonb(details)))
        message = {"vin": event["vin"], "rule": "HARSH_BURST",
                   "severity": severity, "ts": event["ts"], **details}
        producer.produce(
            config.TOPIC_ALERTS, key=event["vin"], value=json.dumps(message).encode()
        )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO alert (vin, rule, severity, raised_at, details) "
            "VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    conn.commit()


def main():
    consumer = Consumer(
        {
            "bootstrap.servers": config.KAFKA_BOOTSTRAP,
            "group.id": "ingest",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([config.TOPIC_RAW])
    producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP, "linger.ms": 20})
    cache = redis.Redis.from_url(config.REDIS_URL)
    conn = psycopg.connect(config.DATABASE_URL)
    rule = HarshBurstRule(
        config.ALERT_WINDOW_S, config.ALERT_THRESHOLD, config.ALERT_COOLDOWN_S
    )
    stats = Counter()
    running = True

    def stop(*_args):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    last_report = last_prune = time.time()
    last_consumed = 0
    print("ingest running, waiting for events...")

    while running:
        messages = consumer.consume(num_messages=500, timeout=1.0)
        if messages:
            valid = []
            for msg in messages:
                if msg.error():
                    stats["kafka_error"] += 1
                    continue
                stats["consumed"] += 1
                event, reason = validate(msg.value() or b"")
                if event is None:
                    producer.produce(
                        config.TOPIC_DLQ,
                        key=msg.key(),
                        value=msg.value(),
                        headers=[("reason", reason.encode())],
                    )
                    stats["dlq"] += 1
                    stats[f"dlq_{reason}"] += 1
                else:
                    valid.append(event)

            if valid:
                pipe = cache.pipeline(transaction=False)
                for event in valid:
                    key = f"dedup:{event['vin']}:{event['seq']}"
                    pipe.set(key, 1, nx=True, ex=config.DEDUP_TTL_S)
                results = pipe.execute()
                fresh = [e for e, is_new in zip(valid, results) if is_new]
                stats["duplicate"] += len(valid) - len(fresh)
                stats["accepted"] += len(fresh)

                alerts = []
                for event in fresh:
                    if event["evt"] in HARSH:
                        count = rule.observe(event["vin"], event["_t"])
                        if count is not None:
                            alerts.append((event, count))
                if alerts:
                    try:
                        write_alerts(conn, producer, alerts)
                        stats["alerts"] += len(alerts)
                    except psycopg.Error as exc:
                        conn.rollback()
                        stats["alert_write_failed"] += 1
                        print("alert write failed:", exc)

            producer.poll(0)
            consumer.commit(asynchronous=False)

        now = time.time()
        if now - last_report >= 5:
            rate = (stats["consumed"] - last_consumed) / (now - last_report)
            counts = " ".join(f"{k}={v}" for k, v in sorted(stats.items()))
            print(f"{rate:8.0f} msg/s | {counts}")
            last_report, last_consumed = now, stats["consumed"]
        if now - last_prune >= 60:
            rule.prune(now)
            last_prune = now

    consumer.close()
    producer.flush(5)
    conn.close()
    print("ingest stopped")


if __name__ == "__main__":
    main()