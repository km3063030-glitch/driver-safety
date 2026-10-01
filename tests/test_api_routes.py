from fastapi import HTTPException
from starlette.requests import Request

from services.api import main


class FakeConnection:
    def __init__(self, results):
        self.results = iter(results)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _sql, _params=()):
        return next(self.results)


def result(row=None, rows=None):
    class Result:
        def fetchone(self):
            return row

        def fetchall(self):
            return rows or []

    return Result()


def make_request():
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    })


def test_limited_user_allows_under_limit_and_rejects_over_limit(monkeypatch):
    class Counter:
        value = 0

        def incr(self, _key):
            self.value += 1
            return self.value

        def expire(self, *_args):
            pass

    counter = Counter()
    monkeypatch.setattr(main, "rds", counter)
    user = {"sub": "manager", "fleet": 4}
    assert main.limited_user(user) == user
    counter.value = main.RATE_LIMIT_PER_MIN
    try:
        main.limited_user(user)
    except HTTPException as error:
        assert error.status_code == 429
    else:
        raise AssertionError("expected rate limit")


def test_limited_user_fails_closed_when_redis_is_unavailable(monkeypatch):
    class BrokenRedis:
        def incr(self, _key):
            raise main.redis.RedisError("private backend detail")

    monkeypatch.setattr(main, "rds", BrokenRedis())
    try:
        main.limited_user({"sub": "manager", "fleet": 4})
    except HTTPException as error:
        assert error.status_code == 503
        assert error.detail == "Rate limit service unavailable"
    else:
        raise AssertionError("expected rate limiter failure")


def test_login_returns_token_for_valid_credentials(monkeypatch):
    class Counter:
        def incr(self, _key):
            return 1

        def expire(self, *_args):
            pass

    monkeypatch.setattr(main, "rds", Counter())
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(row=("stored-hash", 7, "admin"))]),
    )
    monkeypatch.setattr(main, "verify_password", lambda _password, _stored: True)
    response = main.login(main.Login(username="manager1", password="good"), make_request())
    assert response["token_type"] == "bearer"
    assert response["access_token"]


def test_login_returns_generic_401_for_bad_credentials(monkeypatch):
    monkeypatch.setattr(
        main,
        "rds",
        type("Counter", (), {"incr": lambda _self, _key: 1, "expire": lambda *_args: None})(),
    )
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(row=None)]),
    )
    try:
        main.login(main.Login(username="unknown", password="wrong"), make_request())
    except HTTPException as error:
        assert error.status_code == 401
        assert error.detail == "Bad credentials"
    else:
        raise AssertionError("expected authentication failure")


def test_leaderboard_only_returns_vehicles_from_authenticated_fleet(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(rows=[("V1", "D1"), ("V2", "D2"), ("V3", "D3")])]),
    )
    monkeypatch.setattr(main, "all_scores", lambda: {
        "V1": {"vin": "V1", "score": 40.0},
        "V2": {"vin": "V2", "score": 80.0},
        "V3": {"vin": "V3", "score": 60.0},
    })
    response = main.leaderboard(2, 0, "worst", {"fleet": 7})
    assert [row["vin"] for row in response["items"]] == ["V1", "V3"]
    assert response["total"] == 3


def test_vehicle_detail_returns_alerts_and_score(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([
            result(row=("D1",)),
            result(rows=[("HARSH_BURST", "HIGH", "when", {
                "count": 4, "lat": 10.1234, "lon": 78.9876
            })]),
        ]),
    )
    monkeypatch.setattr(main, "all_scores", lambda: {"V1": {"score": 45.0}})
    response = main.vehicle_detail("V1", {"fleet": 7})
    assert response["driver_id"] == "D1"
    assert response["score"]["score"] == 45.0
    assert response["alerts"][0]["severity"] == "HIGH"
    assert response["alerts"][0]["details"]["lat"] == 10.12
    assert response["alerts"][0]["details"]["lon"] == 78.99


def test_vehicle_detail_hides_unowned_vin(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(row=None)]),
    )
    try:
        main.vehicle_detail("OUTSIDE", {"fleet": 7})
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("expected not found")


def test_alerts_are_scoped_to_fleet(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(rows=[(
            "V1", "HARSH_BURST", "HIGH", "when", {"lat": 10.1234, "lon": 78.9876}
        )])]),
    )
    response = main.alerts(10, 0, {"fleet": 7})
    assert response["items"][0]["vin"] == "V1"
    assert response["items"][0]["rule"] == "HARSH_BURST"
    assert response["items"][0]["details"] == {"lat": 10.12, "lon": 78.99}


def test_similar_vehicles_checks_ownership_and_returns_scoped_neighbors(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([
            result(row=(1,)),
            result(rows=[("V2", "D2", 0.25)]),
        ]),
    )
    monkeypatch.setattr(main, "all_scores", lambda: {"V2": {"score": 72.0}})
    response = main.similar("V1", 5, {"fleet": 7})
    assert response["similar"][0] == {
        "vin": "V2", "driver_id": "D2", "distance": 0.25, "score": 72.0
    }


def test_similar_rejects_vehicle_without_fleet_profile(monkeypatch):
    monkeypatch.setattr(
        main.psycopg,
        "connect",
        lambda _url: FakeConnection([result(row=None)]),
    )
    try:
        main.similar("OUTSIDE", 5, {"fleet": 7})
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("expected not found")
