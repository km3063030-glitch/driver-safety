from types import SimpleNamespace

import pytest

from services.simulator import main as simulator


def args(**overrides):
    values = {
        "vehicles": 10, "hz": 1.0, "active": 0.5, "boost": 2.0,
        "duration": 0, "shard": 0, "shards": 1, "burst_every": 0,
        "burst_for": 5, "seed": 9,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_load_vehicles_uses_requested_shard(monkeypatch):
    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            calls.append((sql, params))
            return SimpleNamespace(fetchall=lambda: [("VIN1", 0.25)])

    monkeypatch.setattr(simulator.psycopg, "connect", lambda _url: Connection())
    assert simulator.load_vehicles(100, 2, 4) == [("VIN1", 0.25)]
    assert calls[0][1] == (100, 4, 2)


def test_simulator_exits_clearly_when_no_vehicles(monkeypatch):
    monkeypatch.setattr(simulator, "parse_args", lambda: args())
    monkeypatch.setattr(simulator, "load_vehicles", lambda *_args: [])
    with pytest.raises(SystemExit, match="No vehicles found"):
        simulator.main()


def test_simulator_retries_full_producer_queue_and_flushes_on_interrupt(monkeypatch, capsys):
    sent = []

    class Fleet:
        def __init__(self, *_args, **_kwargs):
            self.active = {"VIN1"}

        def step(self, *_args):
            return [{"vin": "VIN1"}]

    class Noise:
        def __init__(self, *_args):
            pass

        def process(self, _now, event):
            assert event["vin"] == "VIN1"
            return [("VIN1", b"synthetic")]

        def release_due(self, _now):
            return []

    class Producer:
        def __init__(self, _options):
            self.first = True

        def produce(self, topic, value, key, on_delivery):
            if self.first:
                self.first = False
                raise BufferError("queue full")
            sent.append((topic, key, value))

        def poll(self, timeout):
            if timeout == 0:
                raise KeyboardInterrupt

        def flush(self, timeout):
            sent.append(("flush", timeout))

    monkeypatch.setattr(simulator, "parse_args", lambda: args())
    monkeypatch.setattr(simulator, "load_vehicles", lambda *_args: [("VIN1", 0.3)])
    monkeypatch.setattr(simulator, "Fleet", Fleet)
    monkeypatch.setattr(simulator, "Noise", Noise)
    monkeypatch.setattr(simulator, "Producer", Producer)
    monkeypatch.setattr(simulator.time, "time", lambda: 100.0)
    simulator.main()
    assert sent[0] == (simulator.config.TOPIC_RAW, "VIN1", b"synthetic")
    assert sent[1] == ("flush", 10)
    assert "total sent: 1" in capsys.readouterr().out
