from types import SimpleNamespace

from google.genai import types

from services.agent import agent


def test_clean_strips_fleet_and_unsupported_keys():
    schema = {
        "type": "OBJECT",
        "additionalProperties": False,
        "properties": {
            "fleet": {"type": "INTEGER"},
            "vin": {"type": "STRING", "description": "vehicle"},
        },
        "required": ["fleet", "vin"],
    }
    cleaned = agent._clean(schema)
    assert "fleet" not in cleaned["properties"]
    assert cleaned["required"] == ["vin"]
    assert "additionalProperties" not in cleaned


def test_gemini_declarations_are_valid_and_do_not_expose_fleet():
    tool = types.Tool(function_declarations=agent._declarations())
    names = {declaration.name for declaration in tool.function_declarations}
    assert names == set(agent.DISPATCH)
    assert all(
        "fleet" not in (declaration.parameters.properties or {})
        for declaration in tool.function_declarations
    )


def test_run_tool_injects_authoritative_fleet_and_strips_model_fleet(monkeypatch):
    seen = {}

    def fake_tool(vin, fleet):
        seen.update(vin=vin, fleet=fleet)
        return {"vin": vin}

    monkeypatch.setitem(agent.DISPATCH, "test_tool", fake_tool)
    result = agent._run_tool("test_tool", {"vin": "TEST", "fleet": 999}, 42)
    assert seen == {"vin": "TEST", "fleet": 42}
    assert result == {"vin": "TEST"}


def test_run_tool_hides_internal_exceptions(monkeypatch):
    def broken_tool(fleet):
        raise RuntimeError("database password must not leak")

    monkeypatch.setitem(agent.DISPATCH, "broken", broken_tool)
    assert agent._run_tool("broken", {}, 42) == {
        "error": "Tool unavailable; no data was returned"
    }


def test_ask_executes_tool_and_audits_events(monkeypatch):
    call = types.FunctionCall(name="fake_tool", args={"vin": "TEST", "fleet": 999})
    model_content = types.Content(
        role="model", parts=[types.Part(function_call=call)]
    )
    text_content = types.Content(role="model", parts=[types.Part.from_text(text="Safe answer")])

    class FakeClient:
        def __init__(self):
            self.responses = [
                SimpleNamespace(candidates=[SimpleNamespace(content=model_content)], text=None),
                SimpleNamespace(candidates=[SimpleNamespace(content=text_content)], text="Safe answer"),
            ]
            self.models = self

        def generate_content(self, **_kwargs):
            return self.responses.pop(0)

    tool_calls = []
    audit_rows = []

    def fake_tool(vin, fleet):
        tool_calls.append((vin, fleet))
        return {"score": 81}

    monkeypatch.setitem(agent.DISPATCH, "fake_tool", fake_tool)
    monkeypatch.setattr(agent, "_client_or_fail", FakeClient)
    monkeypatch.setattr(
        agent, "audit", lambda username, fleet, action, detail:
        audit_rows.append((username, fleet, action, detail))
    )

    answer = agent.ask("Why this vehicle?", {"fleet": 7, "sub": "manager"})
    assert answer == "Safe answer"
    assert tool_calls == [("TEST", 7)]
    assert [row[2] for row in audit_rows] == ["question", "tool_call", "answer"]
    assert all(row[1] == 7 for row in audit_rows)


def test_audit_failure_stops_before_model_call(monkeypatch):
    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(agent, "audit", fail_audit)
    monkeypatch.setattr(
        agent, "_client_or_fail", lambda: (_ for _ in ()).throw(AssertionError("called"))
    )
    try:
        agent.ask("Tell me about my fleet", {"fleet": 7, "sub": "manager"})
    except RuntimeError as error:
        assert str(error) == "audit unavailable"
    else:
        raise AssertionError("audit failure should stop the request")
