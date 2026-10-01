-- Run these against ClickHouse after loading representative synthetic data.
-- Save the output with machine, data volume, and commit metadata in evidence/.

-- Partition-pruning / index diagnostic for the production scoring window query.
EXPLAIN indexes = 1
SELECT vin,
       countIf(evt = 'HARSH_BRAKE') AS hb,
       countIf(evt = 'HARSH_ACCEL') AS ha,
       countIf(evt = 'HARSH_CORNER') AS hc,
       countIf(evt = 'OVERSPEED') AS os,
       max(odo_km) - min(odo_km) AS km
FROM telemetry.events FINAL
WHERE ts >= now() - INTERVAL 7 DAY
GROUP BY vin;

-- Compare duplicate-aware FINAL reads with a raw table read; do not use the latter
-- for product scoring because the at-least-once writer may have retried events.
EXPLAIN indexes = 1
SELECT count()
FROM telemetry.events
WHERE ts >= now() - INTERVAL 7 DAY;

EXPLAIN indexes = 1
SELECT count()
FROM telemetry.events FINAL
WHERE ts >= now() - INTERVAL 7 DAY;
