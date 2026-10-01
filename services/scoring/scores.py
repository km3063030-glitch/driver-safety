import math
import os

import clickhouse_connect

from services.common import config

WEIGHTS = {"HARSH_BRAKE": 1.0, "HARSH_ACCEL": 0.7, "HARSH_CORNER": 0.7, "OVERSPEED": 0.5}
MIN_KM = 1.0
PRIOR_KM = 10.0
SCALE = float(os.getenv("SCORE_SCALE", "250"))

SQL = """
SELECT vin,
       countIf(evt = 'HARSH_BRAKE')  AS hb,
       countIf(evt = 'HARSH_ACCEL')  AS ha,
       countIf(evt = 'HARSH_CORNER') AS hc,
       countIf(evt = 'OVERSPEED')    AS os,
       max(odo_km) - min(odo_km)     AS km
FROM telemetry.events FINAL
WHERE ts >= now() - INTERVAL {days:UInt32} DAY
GROUP BY vin
HAVING km >= {min_km:Float64}
"""


def get_client():
    return clickhouse_connect.get_client(
        host="localhost",
        port=8123,
        username=config.CLICKHOUSE_USER,
        password=config.CLICKHOUSE_PASSWORD,
    )


def weighted(hb, ha, hc, os_):
    return (
        WEIGHTS["HARSH_BRAKE"] * hb
        + WEIGHTS["HARSH_ACCEL"] * ha
        + WEIGHTS["HARSH_CORNER"] * hc
        + WEIGHTS["OVERSPEED"] * os_
    )


def score_from_rate(rate_per_km):
    return 100.0 * math.exp(-rate_per_km * 100.0 / SCALE)


def compute_scores(days=7, client=None):
    client = client or get_client()
    rows = client.query(
        SQL, parameters={"days": days, "min_km": MIN_KM}
    ).result_rows
    if not rows:
        return []

    total_w = sum(weighted(hb, ha, hc, os_) for _, hb, ha, hc, os_, _ in rows)
    total_km = sum(km for *_, km in rows)
    prior_rate = total_w / total_km

    out = []
    for vin, hb, ha, hc, os_, km in rows:
        w = weighted(hb, ha, hc, os_)
        rate = (w + prior_rate * PRIOR_KM) / (km + PRIOR_KM)
        out.append({
            "vin": vin,
            "score": round(score_from_rate(rate), 1),
            "km": round(km, 1),
            "hb": hb,
            "ha": ha,
            "hc": hc,
            "os": os_,
        })
    return out