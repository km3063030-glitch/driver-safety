import json

from services.common.events import validate

GOOD = {
    "vin": "1HGCM82633A004352", "ts": "2026-10-01T10:15:02.120Z",
    "lat": 21.1702, "lon": 72.8311, "speed_kmh": 64.2,
    "odo_km": 18234.7, "evt": "HARSH_BRAKE", "seq": 88412,
}


def check(**changes):
    return validate(json.dumps({**GOOD, **changes}).encode())


def test_valid_event():
    event, reason = check()
    assert reason is None
    assert event["_t"] > 0


def test_null_evt_allowed():
    assert check(evt=None)[1] is None


def test_rejections():
    assert check(vin="1HGCM82633A004353")[1] == "invalid_vin"
    assert check(ts="yesterday")[1] == "invalid_ts"
    assert check(seq="x")[1] == "invalid_seq"
    assert check(lat=123)[1] == "invalid_lat"
    assert check(evt="DRIFTING")[1] == "invalid_evt"


def test_malformed_and_wrong_shape():
    assert validate(b'{"vin": ')[1] == "malformed_json"
    assert validate(b"")[1] == "malformed_json"
    assert validate(b"[1, 2]")[1] == "not_an_object"