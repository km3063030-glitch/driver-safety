from types import SimpleNamespace

from services.scoring import check


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _sql):
        return SimpleNamespace(fetchall=lambda: self.rows)


def test_scoring_check_reports_rank_correlation(monkeypatch, capsys):
    monkeypatch.setattr(check, "compute_scores", lambda days: [
        {"vin": "V1", "score": 90.0}, {"vin": "V2", "score": 50.0}
    ])
    monkeypatch.setattr(
        check.psycopg,
        "connect",
        lambda _url: FakeConnection([("V1", 0.1), ("V2", 0.9)]),
    )
    check.main()
    output = capsys.readouterr().out
    assert "vehicles scored: 2" in output
    assert "spearman(score, hidden_risk): -1.0" in output


def test_scoring_check_handles_no_scored_vehicles(monkeypatch, capsys):
    monkeypatch.setattr(check, "compute_scores", lambda **_kwargs: [])
    monkeypatch.setattr(
        check.psycopg,
        "connect",
        lambda _url: FakeConnection([("V1", 0.1)]),
    )
    check.main()
    assert "No scored vehicles available" in capsys.readouterr().out
