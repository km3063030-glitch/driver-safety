from types import SimpleNamespace

from services.agent import check


def test_check_prints_configured_model_response(monkeypatch, capsys):
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="OK")

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.models = FakeModels()

    monkeypatch.setattr(check.genai, "Client", FakeClient)
    monkeypatch.setattr(check, "api_key", lambda: "test-key")
    monkeypatch.setattr(check.sys, "argv", ["check"])
    check.main()
    assert captured["model"] == check.MODEL
    assert "OK" in capsys.readouterr().out


def test_check_lists_available_models(monkeypatch, capsys):
    class FakeModels:
        def list(self):
            return [SimpleNamespace(name="models/example")]

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.models = FakeModels()

    monkeypatch.setattr(check.genai, "Client", FakeClient)
    monkeypatch.setattr(check, "api_key", lambda: "test-key")
    monkeypatch.setattr(check.sys, "argv", ["check", "--models"])
    check.main()
    assert "models/example" in capsys.readouterr().out
