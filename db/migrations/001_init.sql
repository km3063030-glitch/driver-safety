CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE fleet (fleet_id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE subscription (
  subscription_id SERIAL PRIMARY KEY,
  fleet_id INT NOT NULL REFERENCES fleet ON DELETE CASCADE,
  plan TEXT NOT NULL, starts_on DATE NOT NULL, ends_on DATE);
CREATE TABLE app_user (
  user_id SERIAL PRIMARY KEY,
  fleet_id INT NOT NULL REFERENCES fleet,
  email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin','manager','viewer')));
CREATE TABLE driver (
  driver_id SERIAL PRIMARY KEY,
  fleet_id INT NOT NULL REFERENCES fleet, full_name TEXT NOT NULL);
CREATE TABLE vehicle_model (
  model_id SERIAL PRIMARY KEY,
  make TEXT NOT NULL, model TEXT NOT NULL, UNIQUE (make, model));
CREATE TABLE vehicle (
  vin CHAR(17) PRIMARY KEY,
  fleet_id INT NOT NULL REFERENCES fleet,
  driver_id INT REFERENCES driver,
  model_id INT NOT NULL REFERENCES vehicle_model);
CREATE TABLE trip (
  trip_id BIGSERIAL PRIMARY KEY,
  vin CHAR(17) NOT NULL REFERENCES vehicle,
  driver_id INT REFERENCES driver,
  started_at TIMESTAMPTZ NOT NULL, ended_at TIMESTAMPTZ, distance_km REAL);
CREATE TABLE alert (
  alert_id BIGSERIAL PRIMARY KEY,
  vin CHAR(17) NOT NULL REFERENCES vehicle,
  rule TEXT NOT NULL, severity TEXT NOT NULL,
  raised_at TIMESTAMPTZ NOT NULL, details JSONB);
CREATE TABLE driver_score (
  driver_id INT REFERENCES driver, score_date DATE,
  score REAL NOT NULL, brake_rate REAL, accel_rate REAL,
  corner_rate REAL, overspeed_pct REAL, night_pct REAL,
  PRIMARY KEY (driver_id, score_date));
CREATE TABLE driver_week_vector (
  driver_id INT REFERENCES driver, week_start DATE,
  features vector(6) NOT NULL, PRIMARY KEY (driver_id, week_start));
CREATE TABLE audit_log (
  audit_id BIGSERIAL PRIMARY KEY, actor TEXT NOT NULL,
  action TEXT NOT NULL, resource TEXT,
  at TIMESTAMPTZ NOT NULL DEFAULT now(), details JSONB);
CREATE TABLE sim_driver_truth (
  driver_id INT PRIMARY KEY REFERENCES driver,
  risk_level REAL NOT NULL);

CREATE INDEX ON vehicle (fleet_id);
CREATE INDEX ON alert (vin, raised_at DESC);
CREATE INDEX ON trip (driver_id, started_at);