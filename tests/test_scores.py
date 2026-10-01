import math
from types import SimpleNamespace

from services.scoring import scores


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, sql, parameters):
        self.calls.append((sql, parameters))
        return SimpleNamespace(result_rows=self.rows)


def test_weighted_rates_and_smooth_score():
    assert scores.weighted(1, 1, 1, 1) == 2.9
    assert scores.score_from_rate(0) == 100.0
    assert math.isclose(
        scores.score_from_rate(0.01), 100 * math.exp(-1 / scores.SCALE)
    )


def test_compute_scores_shrinks_vehicle_rate_toward_fleet_average():
    client = FakeClient([
        ("VIN1", 1, 0, 0, 0, 10.0),
        ("VIN2", 0, 0, 0, 0, 10.0),
    ])
    rows = scores.compute_scores(days=3, client=client)
    assert client.calls[0][1] == {"days": 3, "min_km": scores.MIN_KM}
    assert len(rows) == 2
    assert rows[0]["vin"] == "VIN1"
    assert rows[0]["km"] == 10.0
    assert rows[0]["score"] < rows[1]["score"]
    assert rows[1]["score"] < 100.0


def test_compute_scores_returns_empty_when_query_has_no_rows():
    assert scores.compute_scores(client=FakeClient([])) == []


def test_get_client_uses_configured_clickhouse_credentials(monkeypatch):
    calls = {}

    def fake_get_client(**kwargs):
        calls.update(kwargs)
        return "client"

    monkeypatch.setattr(scores.clickhouse_connect, "get_client", fake_get_client)
    assert scores.get_client() == "client"
    assert calls["username"] == scores.config.CLICKHOUSE_USER
    assert calls["password"] == scores.config.CLICKHOUSE_PASSWORD
