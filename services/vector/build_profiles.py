import numpy as np
import psycopg

from services.common import config
from services.scoring.scores import get_client

SQL = """
SELECT vin,
       countIf(evt='HARSH_BRAKE')  / greatest(max(odo_km)-min(odo_km), 0.1) * 100,
       countIf(evt='HARSH_ACCEL')  / greatest(max(odo_km)-min(odo_km), 0.1) * 100,
       countIf(evt='HARSH_CORNER') / greatest(max(odo_km)-min(odo_km), 0.1) * 100,
       countIf(evt='OVERSPEED')    / greatest(max(odo_km)-min(odo_km), 0.1) * 100,
       avg(speed_kmh), max(speed_kmh)
FROM telemetry.events FINAL
GROUP BY vin
HAVING max(odo_km) - min(odo_km) >= 1.0
"""


def main():
    rows = get_client().query(SQL).result_rows
    if not rows:
        print("profiles written: 0")
        return
    vins = [r[0] for r in rows]
    X = np.array([r[1:] for r in rows], dtype=float)
    X = (X - X.mean(axis=0)) / np.where(X.std(axis=0) == 0, 1, X.std(axis=0))
    data = [(vin, "[" + ",".join(f"{v:.5f}" for v in vec) + "]")
            for vin, vec in zip(vins, X)]
    with psycopg.connect(config.DATABASE_URL) as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO vehicle_profile(vin, embedding) VALUES (%s, %s::vector) "
            "ON CONFLICT (vin) DO UPDATE SET embedding = EXCLUDED.embedding, "
            "updated_at = now()", data)
    print("profiles written:", len(data))


if __name__ == "__main__":
    main()