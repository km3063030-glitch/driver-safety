import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from services.api.security import (
    current_user,
    hash_password,
    make_token,
    verify_password,
)


def test_password_round_trip():
    stored = hash_password("demo1234")
    assert verify_password("demo1234", stored)
    assert not verify_password("wrong", stored)


def test_garbage_token_rejected():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.token")
    with pytest.raises(HTTPException) as exc:
        current_user(creds)
    assert exc.value.status_code == 401


def test_token_carries_fleet_claim():
    token = make_token("manager1", 7, "admin")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert current_user(creds)["fleet"] == 7