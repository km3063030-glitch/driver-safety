"""Synthetic Kafka-compatible producer load test; measures broker acknowledgements."""

import argparse
import json
import random
import time
from datetime import datetime, timezone

import psycopg
from confluent_kafka import Producer

from services.common import config

EVENTS = ("HARSH_BRAKE", "HARSH_ACCEL", "HARSH_CORNER", "OVERSPEED", *([None] * 96))


def load_vins(limit: int) -> list[str]:
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT vin FROM vehicle ORDER BY vin LIMIT %s", (limit,)
        ).fetchall()
    vins = [str(row[0]).strip() for row in rows]
    if not vins:
        raise RuntimeError("No seeded vehicle VINs found; run the database seed first")
    return vins


def make_event(vin: str, seq: int, timestamp: str, rng: random.Random) -> dict:
    return {
        "vin": vin,
        "seq": seq,
        "ts": timestamp,
        "lat": round(rng.uniform(8.0, 13.5), 6),
        "lon": round(rng.uniform(76.0, 80.5), 6),
        "speed_kmh": round(rng.uniform(20.0, 100.0), 2),
        "odo_km": round(1000.0 + seq * 0.01, 3),
        "evt": rng.choice(EVENTS),
    }


def run(args) -> int:
    vins = load_vins(args.vehicles)
    rng = random.Random(args.seed)
    delivered = 0
    errors = []

    def on_delivery(error, _message):
        nonlocal delivered
        if error:
            errors.append(str(error))
        else:
            delivered += 1

    producer = Producer({
        "bootstrap.servers": args.bootstrap,
        "acks": "all",
        "enable.idempotence": True,
        "compression.type": "lz4",
        "linger.ms": 5,
        "batch.num.messages": 10000,
        "message.timeout.ms": 30000,
    })
    total = int(args.rate * args.duration)
    started = time.monotonic()
    next_report = started + 5
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for index in range(total):
        if index % 1000 == 0:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        vin_index = index % len(vins)
        seq = index // len(vins)
        event = make_event(vins[vin_index], seq, timestamp, rng)
        payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
        while True:
            try:
                producer.produce(
                    args.topic,
                    key=event["vin"].encode("ascii"),
                    value=payload,
                    on_delivery=on_delivery,
                )
                break
            except BufferError:
                producer.poll(0.01)
        producer.poll(0)

        elapsed = time.monotonic() - started
        target_elapsed = (index + 1) / args.rate
        if target_elapsed > elapsed:
            time.sleep(target_elapsed - elapsed)
        now = time.monotonic()
        if now >= next_report:
            print(f"sent={index + 1}/{total} acked={delivered} errors={len(errors)}")
            next_report = now + 5

    remaining = producer.flush(60)
    elapsed = time.monotonic() - started
    report = {
        "topic": args.topic,
        "vehicles": len(vins),
        "sent": total,
        "acknowledged": delivered,
        "delivery_errors": len(errors),
        "first_errors": errors[:5],
        "duration_seconds": round(elapsed, 2),
        "acknowledged_events_per_second": round(delivered / elapsed, 2),
        "unflushed_messages": remaining,
    }
    print(json.dumps(report, indent=2))
    return 0 if delivered == total and not errors and remaining == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", default=config.KAFKA_BOOTSTRAP)
    parser.add_argument("--topic", default=config.TOPIC_RAW)
    parser.add_argument("--rate", type=int, default=100_000, help="target events per second")
    parser.add_argument("--duration", type=int, default=300, help="run duration in seconds")
    parser.add_argument("--vehicles", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if args.rate < 1 or args.duration < 1 or args.vehicles < 1:
        parser.error("rate, duration, and vehicles must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
