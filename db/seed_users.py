import psycopg

from services.api.security import hash_password
from services.common import config

with psycopg.connect(config.DATABASE_URL) as conn:
    fleets = [r[0] for r in conn.execute(
        "SELECT fleet_id FROM fleet ORDER BY fleet_id LIMIT 2").fetchall()]
    for i, fid in enumerate(fleets, start=1):
        conn.execute(
            "INSERT INTO app_user(username, password_hash, fleet_id, role) "
            "VALUES (%s, %s, %s, 'admin') ON CONFLICT (username) DO NOTHING",
            (f"manager{i}", hash_password("demo1234"), fid))
    print("fleets used:", fleets)