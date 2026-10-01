import json
import random

from services.common.events import HARSH, validate
from services.common.vin import generate_vin
from services.simulator.fleet import Fleet
from services.simulator.noise import Noise

SAMPLE = {
    "vin": "1HGCM82633A004352", "ts": "2026-10-01T10:15:02.120Z",
    "lat": 21.1702, "lon": 72.8311, "speed_kmh": 64.2,
    "odo_km": 18234.7, "evt": None, "seq": 1,
}


def run_fleet():
    rng = random.Random(7)
    vehicles = [(generate_vin(rng), 0.3) for _ in range(50)]
    fleet = Fleet(vehicles, active_fraction=0.5, boost=50, rng=rng, seq0=1000)
    events = []
    for i in range(300):
        events += fleet.step(1_760_000_000.0 + i, 1.0)
    return fleet, events


def test_fleet_events_are_valid_and_ordered():
    fleet, events = run_fleet()
    assert events
    assert len(fleet.active) <= 25
    last = {}
    for event in events:
        assert validate(json.dumps(event).encode())[1] is None
        assert event["seq"] > last.get(event["vin"], 0)
        last[event["vin"]] = event["seq"]
    assert any(e["evt"] in HARSH for e in events)


def test_duplicates():
    noise = Noise(random.Random(1), dup=1.0, late=0.0, bad=0.0)
    assert len(noise.process(0.0, SAMPLE)) == 2


def test_late_events_are_released_later():
    noise = Noise(random.Random(1), dup=0.0, late=1.0, bad=0.0)
    assert noise.process(0.0, SAMPLE) == []
    assert noise.release_due(1.0) == []
    assert len(noise.release_due(100.0)) == 1


def test_bad_payloads_are_rejected_by_validation():
    noise = Noise(random.Random(2), dup=0.0, late=0.0, bad=1.0)
    for _ in range(20):
        for _key, payload in noise.process(0.0, SAMPLE):
            assert validate(payload)[0] is None