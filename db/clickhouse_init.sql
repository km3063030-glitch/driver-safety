CREATE DATABASE IF NOT EXISTS telemetry;

CREATE TABLE IF NOT EXISTS telemetry.events
(
    vin          String,
    seq          UInt64,
    ts           DateTime64(3, 'UTC'),
    lat          Float64,
    lon          Float64,
    speed_kmh    Float32,
    odo_km       Float32,
    evt          LowCardinality(String),
    ingested_at  DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMMDD(ts)
ORDER BY (vin, ts, seq);