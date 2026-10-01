from types import SimpleNamespace

from services.vector import build_profiles


def test_profile_builder_writes_normalized_vectors(monkeypatch, capsys):
    rows = [
        ("VIN1", 1.0, 2.0, 3.0, 4.0, 50.0, 90.0),
        ("VIN2", 3.0, 1.0, 1.0, 2.0, 70.0, 120.0),
    ]
    monkeypatch.setattr(
        build_profiles,
        "get_client",
        lambda: SimpleNamespace(query=lambda _sql: SimpleNamespace(result_rows=rows)),
    )
    saved = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def executemany(self, sql, params):
            saved.extend(params)
            assert "ON CONFLICT (vin)" in sql

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(build_profiles.psycopg, "connect", lambda _url: Connection())
    build_profiles.main()
    assert [row[0] for row in saved] == ["VIN1", "VIN2"]
    assert all(len(row[1].strip("[]").split(",")) == 6 for row in saved)
    assert "profiles written: 2" in capsys.readouterr().out


def test_profile_builder_handles_no_telemetry_without_database_write(monkeypatch, capsys):
    monkeypatch.setattr(
        build_profiles,
        "get_client",
        lambda: SimpleNamespace(query=lambda _sql: SimpleNamespace(result_rows=[])),
    )
    monkeypatch.setattr(
        build_profiles.psycopg,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected DB write")),
    )
    build_profiles.main()
    assert "profiles written: 0" in capsys.readouterr().out
