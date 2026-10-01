from types import SimpleNamespace

from services.agent import tools


def test_fleet_score_filters_other_fleets_and_calculates_rates(monkeypatch):
    monkeypatch.setattr(tools, "_owned_vins", lambda _fleet: {"OWNED"})
    monkeypatch.setattr(
        tools,
        "compute_scores",
        lambda days: [
            {"vin": "OWNED", "km": 10.0, "hb": 2, "ha": 1, "hc": 0, "os": 1},
            {"vin": "OTHER", "km": 100.0, "hb": 90, "ha": 0, "hc": 0, "os": 0},
        ],
    )
    result, fleet_rate = tools._fleet_scores(8)
    assert set(result) == {"OWNED"}
    assert fleet_rate == 3.2 / 10.0
    assert result["OWNED"]["rates_per_100km"]["HARSH_BRAKE"] == 20.0
    assert result["OWNED"]["fleet_average_weighted_events_per_100km"] == 32.0


def test_vehicle_score_rejects_unowned_vin_before_scoring(monkeypatch):
    monkeypatch.setattr(tools, "_owned_vins", lambda _fleet: {"OWNED"})
    monkeypatch.setattr(
        tools,
        "_fleet_scores",
        lambda _fleet: (_ for _ in ()).throw(AssertionError("must not score")),
    )
    assert tools.get_vehicle_score("OTHER", 8) == {
        "error": "Vehicle not found in your fleet"
    }


def test_recent_alerts_uses_fleet_check_and_caps_limit(monkeypatch):
    calls = []
    alerts = [(
        "HARSH_BURST", "HIGH", "2026-10-01",
        {"count": 4, "lat": 10.1234, "lon": 78.9876},
    )]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            calls.append((sql, params))
            if len(calls) == 1:
                return SimpleNamespace(fetchone=lambda: (1,))
            return SimpleNamespace(fetchall=lambda: alerts)

    monkeypatch.setattr(tools.psycopg, "connect", lambda _url: FakeConnection())
    result = tools.get_recent_alerts("OWNED", 8, 999)
    assert result["vin"] == "OWNED"
    assert result["alerts"][0]["severity"] == "HIGH"
    assert result["alerts"][0]["details"]["lat"] == 10.12
    assert calls[0][1] == ("OWNED", 8)
    assert calls[1][1] == ("OWNED", 8, 20)


def test_recent_alerts_does_not_query_alerts_for_unowned_vin(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, _params):
            return SimpleNamespace(fetchone=lambda: None)

    monkeypatch.setattr(tools.psycopg, "connect", lambda _url: FakeConnection())
    assert tools.get_recent_alerts("OTHER", 8) == {
        "error": "Vehicle not found in your fleet"
    }


def test_find_similar_is_fleet_scoped_and_limits_k(monkeypatch):
    calls = []
    rows = [("NEIGHBOR", "driver-2", 0.12549)]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, params):
            calls.append(params)
            if len(calls) == 1:
                return SimpleNamespace(fetchone=lambda: (1,))
            return SimpleNamespace(fetchall=lambda: rows)

    monkeypatch.setattr(tools.psycopg, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(
        tools,
        "_fleet_scores",
        lambda _fleet: ({"NEIGHBOR": {"score": 72.3}}, 0.1),
    )
    result = tools.find_similar_vehicles("OWNED", 8, 99)
    assert calls == [("OWNED", 8), ("OWNED", 8, "OWNED", 10)]
    assert result["similar"] == [
        {"vin": "NEIGHBOR", "driver_id": "driver-2", "distance": 0.125, "score": 72.3}
    ]


def test_worst_vehicles_sorts_only_fleet_scores(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _sql, params):
            assert params == (8,)
            return SimpleNamespace(fetchall=lambda: [("A", "d1"), ("B", "d2")])

    monkeypatch.setattr(tools.psycopg, "connect", lambda _url: FakeConnection())
    monkeypatch.setattr(
        tools,
        "_fleet_scores",
        lambda _fleet: ({
            "A": {"vin": "A", "score": 80.0},
            "B": {"vin": "B", "score": 30.0},
            "C": {"vin": "C", "score": 1.0},
        }, 0.1),
    )
    result = tools.list_worst_vehicles(8, 1)
    assert result["vehicles"] == [{"vin": "B", "score": 30.0, "driver_id": "d2"}]
