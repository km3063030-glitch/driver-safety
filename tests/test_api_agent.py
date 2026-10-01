import redis
from fastapi.testclient import TestClient

from services.api import main


def test_agent_route_passes_authenticated_user_to_agent(monkeypatch):
    seen = {}
    main.app.dependency_overrides[main.limited_user] = lambda: {
        "sub": "manager1", "fleet": 7, "role": "admin"
    }
    monkeypatch.setattr(
        main,
        "agent_ask",
        lambda question, user: seen.update(question=question, user=user) or "grounded answer",
    )
    try:
        response = TestClient(main.app).post(
            "/agent/ask", json={"question": "Why is this score low?"}
        )
    finally:
        main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"answer": "grounded answer"}
    assert seen["user"]["fleet"] == 7


def test_agent_route_rejects_short_or_long_questions():
    main.app.dependency_overrides[main.limited_user] = lambda: {
        "sub": "manager1", "fleet": 7, "role": "admin"
    }
    try:
        client = TestClient(main.app)
        assert client.post("/agent/ask", json={"question": "hi"}).status_code == 422
        assert client.post("/agent/ask", json={"question": "x" * 501}).status_code == 422
    finally:
        main.app.dependency_overrides.clear()


def test_health_and_cors_preflight():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"ok": True}
    response = client.options(
        "/leaderboard",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_login_rate_limit_blocks_excess_attempts(monkeypatch):
    class LimitedRedis:
        def incr(self, _key):
            return 11

    monkeypatch.setattr(main, "rds", LimitedRedis())
    response = TestClient(main.app).post(
        "/auth/login", json={"username": "manager1", "password": "wrong"}
    )
    assert response.status_code == 429


def test_login_fails_closed_when_rate_limiter_is_unavailable(monkeypatch):
    class BrokenRedis:
        def incr(self, _key):
            raise redis.RedisError("private backend detail")

    monkeypatch.setattr(main, "rds", BrokenRedis())
    response = TestClient(main.app).post(
        "/auth/login", json={"username": "manager1", "password": "wrong"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication service unavailable"
