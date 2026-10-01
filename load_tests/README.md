# Stage 8: performance and recovery tests

These are measurement harnesses, not proof of the hackathon's production targets. Run the 5-minute tests from an EC2 load-generator in the same AWS VPC as the broker. Do not claim the target until the results and consumer-lag evidence are saved under `evidence/`.

## Kafka-compatible broker throughput

1. Start the complete pipeline and confirm the 100,000 seeded vehicles exist:

   ```powershell
   docker compose up -d
   python -m services.common.topics
   python -m services.ingest.main
   ```

   Run ingest and `services.ingest.dlq_sink` in separate terminals. Ensure ClickHouse and Postgres are healthy.

2. In a separate terminal, submit the baseline and burst profiles:

   ```powershell
   python -m load_tests.kafka_throughput --rate 100000 --duration 300
   python -m load_tests.kafka_throughput --rate 300000 --duration 300
   python -m load_tests.kafka_throughput --rate 10000 --duration 3600
   ```

   The harness reads real seeded VINs from Postgres, emits synthetic schema-shaped telemetry, and reports broker delivery acknowledgements and achieved producer rate. The third command is a one-hour soak profile. Run one profile at a time and ensure there is sufficient broker disk space.

3. Record broker acknowledgements, ingest consumer lag at start/peak/end, DLQ counts, ClickHouse row counts before/after, and measured ingest-to-query latency. The harness alone does **not** prove consumer throughput, no loss, or the dashboard/alert latency SLAs. Compare `FINAL` rows by `(vin, seq)` before and after; allow in-flight events to drain before the final query.

## Recovery / chaos check

Run only against disposable test data. With ingest running and a small producer load active:

```powershell
docker compose kill redpanda
docker compose start redpanda
docker compose ps
```

Record the broker outage, consumer restart/reconnect behavior, consumer lag, DLQ counts, and ClickHouse final row count after recovery. This single-node local Compose broker has no replication, so this is a process-restart check—not a high-availability or broker-loss durability proof. Never claim zero loss without comparing produced and consumed IDs.

## Evidence to retain

For every run save date/commit, machine type, region, test duration, target and achieved rates, producer acknowledgements, consumer lag, errors/DLQ count, latency percentiles, and the raw test output. Redact credentials and public IPs before committing results.
