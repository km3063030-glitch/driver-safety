CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS vehicle_profile (
    vin        CHAR(17) PRIMARY KEY REFERENCES vehicle(vin),
    embedding  vector(6) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);