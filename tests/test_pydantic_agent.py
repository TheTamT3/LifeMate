import sys
import types
from contextlib import asynccontextmanager

import pytest
from pydantic import ValidationError

from lifemate.pydantic_agent import (
    AgentDependencies,
    build_tool_definitions,
    catalog_argument_model,
    run_agent,
    validate_catalog_arguments,
)


def _tool(**parameters):
    return {
        "name": "calendar.create_event",
        "kind": "write",
        "description": "Tạo sự kiện",
        "parameters": parameters,
    }


def test_catalog_argument_model_enforces_required_enum_and_range():
    tool = _tool(
        type="object",
        properties={
            "mode": {"type": "string", "enum": ["on", "off"]},
            "amount": {"type": "integer", "exclusiveMinimum": 0},
        },
        required=["mode", "amount"],
    )
    model = catalog_argument_model(tool)
    assert model.model_validate({"mode": "on", "amount": 2}).amount == 2
    with pytest.raises(ValidationError):
        model.model_validate({"mode": "invalid", "amount": 2})
    with pytest.raises(ValidationError):
        model.model_validate({"mode": "on", "amount": 0})


def test_catalog_argument_model_supports_nested_object_array():
    tool = _tool(
        type="object",
        properties={
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"item_id": {"type": "string"}, "quantity": {"type": "integer"}},
                    "required": ["item_id", "quantity"],
                },
            }
        },
        required=["items"],
    )
    model = catalog_argument_model(tool)
    value = model.model_validate({"items": [{"item_id": "i1", "quantity": 2}]})
    assert value.items[0].item_id == "i1"
    with pytest.raises(ValidationError):
        model.model_validate({"items": [{"item_id": "i1"}]})


def test_x_one_of_requires_one_complete_group():
    tool = _tool(
        type="object",
        properties={"contact_id": {"type": "string"}, "phone": {"type": "string"}},
        required=[],
        **{"x-one-of": [["contact_id"], ["phone"]]},
    )
    assert validate_catalog_arguments(tool, {"contact_id": "c1"}) == {"contact_id": "c1"}
    with pytest.raises(ValueError, match="x-one-of"):
        validate_catalog_arguments(tool, {})


def test_catalog_format_is_validated_before_environment_call():
    tool = _tool(
        type="object",
        properties={"when": {"type": "string", "format": "date"}},
        required=["when"],
    )
    assert validate_catalog_arguments(tool, {"when": "2026-10-28"}) == {"when": "2026-10-28"}
    with pytest.raises(ValueError, match="invalid date"):
        validate_catalog_arguments(tool, {"when": "not-a-date"})


def test_tool_factory_keeps_description_and_calls_official_name(monkeypatch):
    class FakeTool:
        def __init__(self, function, name, description, json_schema):
            self.function = function
            self.name = name
            self.description = description
            self.json_schema = json_schema

        @classmethod
        def from_schema(cls, function, name, description, json_schema, takes_ctx, sequential):
            return cls(function, name, description, json_schema)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    calls = []

    class FakeEnv:
        def call(self, name, arguments):
            calls.append((name, arguments))
            return {"ok": True}

    tool = _tool(type="object", properties={"title": {"type": "string"}}, required=["title"])
    tool["kind"] = "read"
    definitions = build_tool_definitions(AgentDependencies(FakeEnv(), {tool["name"]: tool}, 8))
    assert len(definitions) == 1
    assert definitions[0].name != tool["name"]
    assert tool["description"] in definitions[0].description
    assert tool["name"] in definitions[0].description
    assert definitions[0].json_schema["type"] == "object"
    definitions[0].function(None, title="x")
    assert calls == [(tool["name"], {"title": "x"})]


def test_write_tool_records_kind_after_environment_call(monkeypatch):
    class FakeTool:
        @classmethod
        def from_schema(cls, function, name, description, json_schema, takes_ctx, sequential):
            return types.SimpleNamespace(function=function, name=name, description=description)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    calls = []

    class FakeEnv:
        def call(self, name, arguments):
            calls.append((name, arguments))
            return {"ok": True}

    tool = _tool(type="object", properties={}, required=[])
    deps = AgentDependencies(FakeEnv(), {tool["name"]: tool}, 8)
    definition = build_tool_definitions(deps)[0]
    definition.function(None)
    assert calls == [(tool["name"], {})]
    assert deps.calls[0]["kind"] == "write"


def test_run_agent_passes_deterministic_settings_and_round_limit():
    class FakeAgent:
        def __init__(self):
            self.kwargs = None

        def run_sync(self, prompt, **kwargs):
            self.kwargs = kwargs
            return None

    deps = AgentDependencies(object(), {}, max_steps=8, seed=7)
    agent = FakeAgent()
    run_agent(agent, deps, "request")
    assert agent.kwargs["deps"] is deps
    assert agent.kwargs["usage_limits"].request_limit == 8
    assert agent.kwargs["model_settings"] == {"temperature": 0, "top_p": 1, "seed": 7}


def test_iter_runner_preserves_same_response_calls_and_stops_after_write():
    class FakeRun:
        def __init__(self, deps):
            self.deps = deps
            self.next_node = types.SimpleNamespace()
            self.steps = 0
            self.result = "done"

        async def next(self, _node):
            self.steps += 1
            if self.steps == 1:
                self.deps.calls.append({"name": "contacts.search", "kind": "read"})
            elif self.steps == 2:
                # Both calls belong to one model response and must be retained.
                self.deps.calls.extend(
                    [
                        {"name": "calendar.create_event", "kind": "write"},
                        {"name": "sys.ask_missing_info", "kind": "meta"},
                    ]
                )
            else:
                raise AssertionError("runner requested an extra model round")
            return types.SimpleNamespace()

    class FakeAgent:
        def __init__(self):
            self.run = None

        @asynccontextmanager
        async def iter(self, _prompt, *, deps, **_kwargs):
            self.run = FakeRun(deps)
            yield self.run

    deps = AgentDependencies(object(), {}, max_steps=8)
    agent = FakeAgent()
    assert run_agent(agent, deps, "request") == "done"
    assert agent.run.steps == 2
    assert [call["kind"] for call in deps.calls] == ["read", "write", "meta"]
