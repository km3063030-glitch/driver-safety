import pytest

from services.agent import settings


def test_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        settings.api_key()


def test_api_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "  test-key  ")
    assert settings.api_key() == "test-key"