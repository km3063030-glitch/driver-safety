import argparse
import random
import time

import psycopg
from confluent_kafka import Producer

from services.common import config
from services.simulator.fleet import Fleet
from services.simulator.noise import Noise


def load_vehicles(total, shard, shards):
    sql = (
        "SELECT v.vin, t.risk_level FROM vehicle v "
        "JOIN sim_driver_truth t ON t.driver_id = v.driver_id "
        "WHERE v.driver_id <= %s AND v.driver_id %% %s = %s "
        "ORDER BY v.driver_id"
    )
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(sql, (total, shards, shard)).fetchall()
    return [(vin, float(risk)) for vin, risk in rows]


def parse_args():
    p = argparse.ArgumentParser(description="Connected-vehicle telemetry simulator")
    p.add_argument("--vehicles", type=int, default=2000, help="total vehicles")
    p.add_argument("--hz", type=float, default=1.0, help="events/sec per active vehicle")
    p.add_argument("--active", type=float, default=0.15, help="fraction driving")
    p.add_argument("--boost", type=float, default=4.0, help="harsh-event rate multiplier")
    p.add_argument("--duration", type=int, default=0, help="seconds, 0 = until Ctrl+C")
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--shards", type=int, default=1)
    p.add_argument("--burst-every", type=int, default=0, help="seconds, 0 = off")
    p.add_argument("--burst-for", type=int, default=60)
    p.add_argument("--seed", type=int, default=0, help="0 = random")
    return p.parse_args()


def main():
    args = parse_args()
    rng = random.Random(args.seed + args.shard if args.seed else None)
    vehicles = load_vehicles(args.vehicles, args.shard, args.shards)
    if not vehicles:
        raise SystemExit("No vehicles found. Did you run: python -m db.seed ?")
    fleet = Fleet(vehicles, args.active, args.boost, rng, seq0=int(time.time() * 1000))
    noise = Noise(rng)
    producer = Producer(
        {
            "bootstrap.servers": config.KAFKA_BOOTSTRAP,
            "linger.ms": 20,
            "batch.num.messages": 10000,
            "compression.type": "lz4",
            "queue.buffering.max.messages": 500000,
        }
    )
    sent = 0
    failed = 0

    def on_delivery(err, _msg):
        nonlocal failed
        if err is not None:
            failed += 1

    def send(key, payload):
        nonlocal sent
        while True:
            try:
                producer.produce(
                    config.TOPIC_RAW, value=payload, key=key, on_delivery=on_delivery
                )
                break
            except BufferError:
                producer.poll(0.05)
        sent += 1

    print(f"shard {args.shard}/{args.shards}: {len(vehicles)} vehicles")
    start = time.time()
    end = start + args.duration if args.duration else float("inf")
    next_tick = start
    last_report, last_sent, behind = start, 0, 0
    try:
        while time.time() < end:
            now = time.time()
            elapsed = now - start
            bursting = (
                args.burst_every > 0
                and elapsed >= args.burst_every
                and (elapsed % args.burst_every) < args.burst_for
            )
            step = 1.0 / (args.hz * (3 if bursting else 1))
            for event in fleet.step(now, step):
                for key, payload in noise.process(now, event):
                    send(key, payload)
            for key, payload in noise.release_due(now):
                send(key, payload)
            producer.poll(0)
            next_tick += step
            delay = next_tick - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.time()
                behind += 1
            if now - last_report >= 5:
                rate = (sent - last_sent) / (now - last_report)
                note = " | BURST" if bursting else ""
                if behind:
                    note += " | behind schedule, add shards"
                print(
                    f"[{elapsed:5.0f}s] {rate:8.0f} msg/s | "
                    f"active {len(fleet.active)} | failed {failed}{note}"
                )
                last_report, last_sent, behind = now, sent, 0
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        print("stopped, total sent:", sent)


if __name__ == "__main__":
    main()