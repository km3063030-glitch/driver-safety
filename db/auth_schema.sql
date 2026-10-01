CREATE TABLE IF NOT EXISTS app_user (
    user_id       SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    fleet_id      INT NOT NULL REFERENCES fleet(fleet_id),
    role          TEXT NOT NULL DEFAULT 'viewer'
);