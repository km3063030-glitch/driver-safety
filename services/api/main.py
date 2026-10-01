import hashlib
import time

import psycopg
import redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.agent.agent import ask as agent_ask
from services.api.security import current_user, make_token, verify_password
from services.common import config
from services.common.privacy import mask_location
from services.scoring.scores import compute_scores

app = FastAPI(title="Driver Safety API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.API_CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
rds = redis.Redis.from_url(config.REDIS_URL)
RATE_LIMIT_PER_MIN = 60
LOGIN_RATE_LIMIT_PER_MIN = 10

_cache = {"at": 0.0, "rows": {}}


def all_scores():
    if time.time() - _cache["at"] > 30:
        _cache["rows"] = {r["vin"]: r for r in compute_scores(days=7)}
        _cache["at"] = time.time()
    return _cache["rows"]


def limited_user(user=Depends(current_user)):
    key = f"rl:{user['sub']}:{int(time.time() // 60)}"
    try:
        count = rds.incr(key)
        if count == 1:
            rds.expire(key, 60)
    except redis.RedisError as exc:
        raise HTTPException(503, "Rate limit service unavailable") from exc
    if count > RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Rate limit exceeded")
    return user


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class AgentQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/login")
def login(body: Login, request: Request):
    remote_ip = request.client.host if request.client else "unknown"
    identity = hashlib.sha256(body.username.strip().lower().encode()).hexdigest()
    bucket = int(time.time() // 60)
    ip_key = f"login:ip:{remote_ip}:{bucket}"
    user_key = f"login:user:{identity}:{bucket}"
    try:
        ip_attempts = rds.incr(ip_key)
        user_attempts = rds.incr(user_key)
        if ip_attempts == 1:
            rds.expire(ip_key, 60)
        if user_attempts == 1:
            rds.expire(user_key, 60)
    except redis.RedisError as exc:
        raise HTTPException(503, "Authentication service unavailable") from exc
    if max(ip_attempts, user_attempts) > LOGIN_RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Too many login attempts")
    with psycopg.connect(config.DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT password_hash, fleet_id, role FROM app_user WHERE username = %s",
            (body.username,)).fetchone()
    if not row or not verify_password(body.password, row[0]):
        raise HTTPException(401, "Bad credentials")
    return {"access_token": make_token(body.username, row[1], row[2]),
            "token_type": "bearer"}


@app.get("/leaderboard")
def leaderboard(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order: str = Query("worst", pattern="^(worst|best)$"),
    user=Depends(limited_user),
):
    with psycopg.connect(config.DATABASE_URL) as conn:
        fleet_vehicles = conn.execute(
            "SELECT vin, driver_id FROM vehicle WHERE fleet_id = %s",
            (user["fleet"],)).fetchall()
    scores = all_scores()
    rows = [{**scores[vin], "driver_id": driver_id}
            for vin, driver_id in fleet_vehicles if vin in scores]
    rows.sort(key=lambda r: r["score"], reverse=(order == "best"))
    return {"total": len(rows), "items": rows[offset:offset + limit]}


@app.get("/vehicles/{vin}")
def vehicle_detail(vin: str, user=Depends(limited_user)):
    with psycopg.connect(config.DATABASE_URL) as conn:
        row = conn.execute(
            "SELECT driver_id FROM vehicle WHERE vin = %s AND fleet_id = %s",
            (vin, user["fleet"])).fetchone()
        if not row:
            raise HTTPException(404, "Vehicle not found")
        alerts = conn.execute(
            "SELECT rule, severity, raised_at, details FROM alert "
            "WHERE vin = %s ORDER BY raised_at DESC LIMIT 20", (vin,)).fetchall()
    return {
        "vin": vin,
        "driver_id": row[0],
        "score": all_scores().get(vin),
        "alerts": [{"rule": a, "severity": b, "raised_at": c, "details": mask_location(d)}
                   for a, b, c, d in alerts],
    }


@app.get("/alerts")
def alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(limited_user),
):
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT a.vin, a.rule, a.severity, a.raised_at, a.details "
            "FROM alert a JOIN vehicle v ON v.vin = a.vin "
            "WHERE v.fleet_id = %s ORDER BY a.raised_at DESC LIMIT %s OFFSET %s",
            (user["fleet"], limit, offset)).fetchall()
    return {"items": [{"vin": a, "rule": b, "severity": c, "raised_at": d,
                       "details": mask_location(e)}
                      for a, b, c, d, e in rows]}


@app.get("/vehicles/{vin}/similar")
def similar(vin: str, k: int = Query(5, ge=1, le=20), user=Depends(limited_user)):
    with psycopg.connect(config.DATABASE_URL) as conn:
        own = conn.execute(
            "SELECT 1 FROM vehicle_profile p JOIN vehicle v ON v.vin = p.vin "
            "WHERE p.vin = %s AND v.fleet_id = %s",
            (vin, user["fleet"]),
        ).fetchone()
        if not own:
            raise HTTPException(404, "Vehicle not found")

        rows = conn.execute(
            "SELECT p.vin, v.driver_id, p.embedding <-> "
            "(SELECT embedding FROM vehicle_profile WHERE vin = %s) AS dist "
            "FROM vehicle_profile p JOIN vehicle v ON v.vin = p.vin "
            "WHERE v.fleet_id = %s AND p.vin <> %s ORDER BY dist LIMIT %s",
            (vin, user["fleet"], vin, k),
        ).fetchall()

    scores = all_scores()
    return {
        "vin": vin,
        "similar": [
            {
                "vin": a,
                "driver_id": b,
                "distance": round(float(c), 3),
                "score": scores.get(a, {}).get("score"),
            }
            for a, b, c in rows
        ],
    }


@app.post("/agent/ask")
def agent_endpoint(body: AgentQuestion, user=Depends(limited_user)):
    return {"answer": agent_ask(body.question, user)}