"""Read-only, fleet-scoped data tools for the safety assistant."""

import psycopg

from services.common import config
from services.common.privacy import mask_location
from services.scoring.scores import (
    PRIOR_KM,
    compute_scores,
    score_from_rate,
    weighted,
)


def _owned_vins(fleet: int) -> set[str]:
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT vin FROM vehicle WHERE fleet_id = %s", (fleet,)
        ).fetchall()
    return {str(row[0]).strip() for row in rows}


def _fleet_scores(fleet: int) -> tuple[dict[str, dict], float]:
    """Return only this fleet's telemetry scores and its weighted fleet rate."""
    owned = _owned_vins(fleet)
    rows = [row for row in compute_scores(days=7) if str(row["vin"]).strip() in owned]
    km_total = sum(float(row["km"]) for row in rows)
    weighted_total = sum(
        weighted(row["hb"], row["ha"], row["hc"], row["os"]) for row in rows
    )
    fleet_rate = weighted_total / km_total if km_total else 0.0

    result = {}
    for row in rows:
        km = float(row["km"])
        events = weighted(row["hb"], row["ha"], row["hc"], row["os"])
        rate = events / km if km else 0.0
        shrunk_rate = (events + fleet_rate * PRIOR_KM) / (km + PRIOR_KM)
        result[str(row["vin"]).strip()] = {
            **row,
            "score": round(score_from_rate(shrunk_rate), 1),
            "weighted_events_per_100km": round(rate * 100, 2),
            "fleet_average_weighted_events_per_100km": round(fleet_rate * 100, 2),
            "rates_per_100km": {
                event: round(float(row[field]) / km * 100, 2) if km else 0.0
                for event, field in (
                    ("HARSH_BRAKE", "hb"),
                    ("HARSH_ACCEL", "ha"),
                    ("HARSH_CORNER", "hc"),
                    ("OVERSPEED", "os"),
                )
            },
        }
    return result, fleet_rate


def get_vehicle_score(vin: str, fleet: int) -> dict:
    """Get one vehicle's seven-day score; never return cross-fleet data."""
    canonical_vin = vin.strip()
    owned = _owned_vins(fleet)
    if canonical_vin not in owned:
        return {"error": "Vehicle not found in your fleet"}
    scores, _ = _fleet_scores(fleet)
    result = scores.get(canonical_vin)
    if result is None:
        return {"error": "No recent score is available for this vehicle"}
    return result


def get_recent_alerts(vin: str, fleet: int, limit: int = 5) -> dict:
    """Read a bounded number of recent alerts for an owned vehicle."""
    limit = max(1, min(int(limit), 20))
    canonical_vin = vin.strip()
    with psycopg.connect(config.DATABASE_URL) as conn:
        owned = conn.execute(
            "SELECT 1 FROM vehicle WHERE vin = %s AND fleet_id = %s",
            (canonical_vin, fleet),
        ).fetchone()
        if not owned:
            return {"error": "Vehicle not found in your fleet"}
        rows = conn.execute(
            "SELECT a.rule, a.severity, a.raised_at, a.details "
            "FROM alert a JOIN vehicle v ON v.vin = a.vin "
            "WHERE a.vin = %s AND v.fleet_id = %s "
            "ORDER BY a.raised_at DESC LIMIT %s",
            (canonical_vin, fleet, limit),
        ).fetchall()
    return {
        "vin": canonical_vin,
        "alerts": [
            {
                "rule": rule,
                "severity": severity,
                "raised_at": at,
                "details": mask_location(details),
            }
            for rule, severity, at, details in rows
        ],
    }


def find_similar_vehicles(vin: str, fleet: int, k: int = 5) -> dict:
    """Find nearest vehicle profiles, restricted to the caller's fleet."""
    k = max(1, min(int(k), 10))
    canonical_vin = vin.strip()
    with psycopg.connect(config.DATABASE_URL) as conn:
        own = conn.execute(
            "SELECT 1 FROM vehicle_profile p JOIN vehicle v ON v.vin = p.vin "
            "WHERE p.vin = %s AND v.fleet_id = %s",
            (canonical_vin, fleet),
        ).fetchone()
        if not own:
            return {"error": "Vehicle profile not found in your fleet"}
        rows = conn.execute(
            "SELECT p.vin, v.driver_id, p.embedding <-> "
            "(SELECT embedding FROM vehicle_profile WHERE vin = %s) AS dist "
            "FROM vehicle_profile p JOIN vehicle v ON v.vin = p.vin "
            "WHERE v.fleet_id = %s AND p.vin <> %s "
            "ORDER BY dist LIMIT %s",
            (canonical_vin, fleet, canonical_vin, k),
        ).fetchall()
    scores, _ = _fleet_scores(fleet)
    return {
        "vin": canonical_vin,
        "similar": [
            {
                "vin": str(other_vin).strip(),
                "driver_id": driver_id,
                "distance": round(float(distance), 3),
                "score": scores.get(str(other_vin).strip(), {}).get("score"),
            }
            for other_vin, driver_id, distance in rows
        ],
    }


def list_worst_vehicles(fleet: int, limit: int = 5) -> dict:
    """List the lowest-scoring vehicles in the caller's fleet."""
    limit = max(1, min(int(limit), 10))
    scores, _ = _fleet_scores(fleet)
    with psycopg.connect(config.DATABASE_URL) as conn:
        drivers = conn.execute(
            "SELECT vin, driver_id FROM vehicle WHERE fleet_id = %s", (fleet,)
        ).fetchall()
    items = [
        {**scores[str(vin).strip()], "driver_id": driver_id}
        for vin, driver_id in drivers
        if str(vin).strip() in scores
    ]
    items.sort(key=lambda item: item["score"])
    return {"vehicles": items[:limit]}


DISPATCH = {
    "get_vehicle_score": get_vehicle_score,
    "get_recent_alerts": get_recent_alerts,
    "find_similar_vehicles": find_similar_vehicles,
    "list_worst_vehicles": list_worst_vehicles,
}

TOOLS = [
    {
        "name": "get_vehicle_score",
        "description": "Get a vehicle's recent safety score, event rates and fleet average.",
        "input_schema": {
            "type": "OBJECT",
            "properties": {"vin": {"type": "STRING", "description": "17-character VIN"}},
            "required": ["vin"],
        },
    },
    {
        "name": "get_recent_alerts",
        "description": "Get recent safety alerts for a vehicle in the user's fleet.",
        "input_schema": {
            "type": "OBJECT",
            "properties": {
                "vin": {"type": "STRING"},
                "limit": {"type": "INTEGER", "minimum": 1, "maximum": 20},
            },
            "required": ["vin"],
        },
    },
    {
        "name": "find_similar_vehicles",
        "description": "Find behaviorally similar vehicles in the user's fleet.",
        "input_schema": {
            "type": "OBJECT",
            "properties": {
                "vin": {"type": "STRING"},
                "k": {"type": "INTEGER", "minimum": 1, "maximum": 10},
            },
            "required": ["vin"],
        },
    },
    {
        "name": "list_worst_vehicles",
        "description": "List the lowest-scoring vehicles in the user's fleet.",
        "input_schema": {
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "minimum": 1, "maximum": 10}},
        },
    },
]
