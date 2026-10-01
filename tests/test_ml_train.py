import numpy as np
import pandas as pd
import pytest

from services.ml import train


def make_windows():
    rows = []
    risky = {2, 7, 12, 18}
    for index in range(20):
        for bucket in range(1, 5):
            rows.append({
                "vin": f"VIN{index:02d}",
                "b": bucket,
                "hb": int(index in risky),
                "ha": 0,
                "hc": 0,
                "os": 0,
                "km": 0.2,
                "avg_speed": 40.0 + index,
                "max_speed": 60.0 + index,
            })
    return pd.DataFrame(rows)


def test_build_creates_next_window_labels(monkeypatch, capsys):
    monkeypatch.setattr(
        train,
        "get_client",
        lambda: type("Client", (), {"query_df": lambda *_args, **_kwargs: make_windows()})(),
    )
    pairs = train.build()
    assert len(pairs) == 20
    assert set(pairs.label.unique()) == {False, True}
    assert "hist_rate" in pairs
    assert "rate_next" in pairs
    assert "rows: 80" in capsys.readouterr().out


def test_build_empty_data_returns_no_pairs(monkeypatch):
    empty = make_windows().iloc[0:0]
    monkeypatch.setattr(
        train,
        "get_client",
        lambda: type("Client", (), {"query_df": lambda *_args, **_kwargs: empty.copy()})(),
    )
    assert train.build().empty


def test_precision_at_k():
    y = np.array([0, 1, 1, 0])
    score = np.array([0.1, 0.9, 0.8, 0.7])
    assert train.precision_at_k(y, score, 2) == 1.0


def test_main_fails_clearly_without_window_pairs(monkeypatch):
    monkeypatch.setattr(train, "build", lambda: pd.DataFrame())
    with pytest.raises(SystemExit, match="No window pairs"):
        train.main()


def test_main_trains_baseline_and_models(monkeypatch, capsys):
    data = pd.DataFrame({
        "vin": [f"VIN{index:02d}" for index in range(20)],
        "label": [index in {2, 7, 12, 18} for index in range(20)],
        "hb": [int(index in {2, 7, 12, 18}) for index in range(20)],
        "ha": [index % 3 for index in range(20)],
        "hc": [index % 2 for index in range(20)],
        "os": [index % 4 for index in range(20)],
        "km": [1.0 + index / 10 for index in range(20)],
        "rate": [float(index) for index in range(20)],
        "avg_speed": [35.0 + index for index in range(20)],
        "max_speed": [55.0 + index for index in range(20)],
        "hist_rate": [float(index) / 2 for index in range(20)],
    })

    class FixedSplit:
        def __init__(self, **_kwargs):
            pass

        def split(self, *_args, **_kwargs):
            yield np.arange(10), np.arange(10, 20)

    monkeypatch.setattr(train, "build", lambda: data)
    monkeypatch.setattr(train, "GroupShuffleSplit", FixedSplit)
    train.main()
    output = capsys.readouterr().out
    assert "logistic regression" in output
    assert "gradient boosting" in output
    assert "random precision" in output
