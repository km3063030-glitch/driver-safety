CREATE TABLE IF NOT EXISTS fleet (
    fleet_id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE);

CREATE TABLE IF NOT EXISTS driver (
    driver_id TEXT PRIMARY KEY,
    fleet_id INT NOT NULL REFERENCES fleet,
    name TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS vehicle (
    vin CHAR(17) PRIMARY KEY,
    fleet_id INT NOT NULL REFERENCES fleet,
    driver_id TEXT REFERENCES driver);

CREATE INDEX IF NOT EXISTS idx_vehicle_fleet ON vehicle(fleet_id);
CREATE INDEX IF NOT EXISTS idx_driver_fleet ON driver(fleet_id);

-- simulator ground truth, kept out of the product tables on purpose
CREATE TABLE IF NOT EXISTS sim_driver_truth (
    driver_id TEXT PRIMARY KEY REFERENCES driver,
    hidden_risk REAL NOT NULL);