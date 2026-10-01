import json
import random

from load_tests.kafka_throughput import make_event


def test_load_harness_emits_schema_shaped_synthetic_event():
    event = make_event(
        "1HGCM82633A004352",
        12,
        "2026-10-01T12:00:00Z",
        random.Random(1),
    )
    assert set(event) == {
        "vin", "seq", "ts", "lat", "lon", "speed_kmh", "odo_km", "evt"
    }
    assert event["vin"] == "1HGCM82633A004352"
    assert event["seq"] == 12
    assert event["evt"] in {"HARSH_BRAKE", "HARSH_ACCEL", "HARSH_CORNER", "OVERSPEED", None}
    assert json.loads(json.dumps(event)) == event
