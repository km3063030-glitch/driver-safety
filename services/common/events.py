import json
from datetime import datetime

from services.common.vin import is_valid_vin

VALID_EVENTS = {
    "HARSH_BRAKE", "HARSH_ACCEL", "HARSH_CORNER", "OVERSPEED",
    "IDLE_START", "IGNITION_ON", "IGNITION_OFF",
}
HARSH = {"HARSH_BRAKE", "HARSH_ACCEL", "HARSH_CORNER"}
RANGES = (("lat", -90, 90), ("lon", -180, 180), ("speed_kmh", 0, 400))


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def validate(raw):
    """Return (event, None) if valid, else (None, reason)."""
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        return None, "malformed_json"
    if not isinstance(event, dict):
        return None, "not_an_object"
    vin = event.get("vin")
    if not isinstance(vin, str) or not is_valid_vin(vin):
        return None, "invalid_vin"
    try:
        event["_t"] = parse_ts(event["ts"])
    except (KeyError, ValueError, AttributeError, TypeError):
        return None, "invalid_ts"
    seq = event.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool):
        return None, "invalid_seq"
    for key, low, high in RANGES:
        value = event.get(key)
        if not _is_number(value) or not low <= value <= high:
            return None, f"invalid_{key}"
    evt = event.get("evt")
    if evt is not None and evt not in VALID_EVENTS:
        return None, "invalid_evt"
    return event, None