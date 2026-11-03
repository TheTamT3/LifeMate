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


def test_email_format_accepts_valid_literal_and_preserves_single_recipient():
    tool = _tool(type="object", properties={"email": {"type": "string", "format": "email"}}, required=["email"])
    value = "a.b+tag@example.com"
    arguments = {"email": value}
    assert validate_catalog_arguments(tool, arguments) == arguments
    assert arguments == {"email": value}


@pytest.mark.parametrize("value", ["a b@example.com", "a@example", "a@b.com\n", "a@@b.com"])
def test_email_format_rejects_malformed_literal(value):
    tool = _tool(type="object", properties={"email": {"type": "string", "format": "email"}}, required=["email"])
    with pytest.raises(ValueError, match="invalid email"):
        validate_catalog_arguments(tool, {"email": value})


def test_email_array_validation_does_not_add_recipients():
    tool = _tool(type="object", properties={"emails": {"type": "array", "items": {"type": "string", "format": "email"}}})
    arguments = {"emails": ["a@example.com"]}
    assert validate_catalog_arguments(tool, arguments) == arguments


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
    assert definitions[0].name == "calendar_create_event"
    assert tool["description"] in definitions[0].description
    assert tool["name"] in definitions[0].description
    assert definitions[0].json_schema["type"] == "object"
    definitions[0].function(None, title="x")
    assert calls == [(tool["name"], {"title": "x"})]


@pytest.mark.parametrize("parameters", [None, {}, {"type": "object", "properties": {}}])
def test_parameterless_tool_description_requires_empty_arguments(monkeypatch, parameters):
    class FakeTool:
        @classmethod
        def from_schema(cls, function, **kwargs):
            return types.SimpleNamespace(function=function, **kwargs)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    tool = {"name": "ewallet.get_balance", "description": "Số dư ví", "parameters": parameters}
    definition = build_tool_definitions(AgentDependencies(None, {tool["name"]: tool}, 8))[0]
    assert tool["description"] in definition.description
    assert 'Luôn gọi với arguments {}' in definition.description
    assert 'Không truyền bất kỳ trường nào' in definition.description
    assert definition.json_schema["additionalProperties"] is False
    assert validate_catalog_arguments(tool, {}) == {}
    with pytest.raises(ValidationError):
        validate_catalog_arguments(tool, {"amount": "0"})


def test_optional_parameter_tool_does_not_require_empty_arguments(monkeypatch):
    class FakeTool:
        @classmethod
        def from_schema(cls, function, **kwargs):
            return types.SimpleNamespace(function=function, **kwargs)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    tool = _tool(type="object", properties={"query": {"type": "string"}}, required=[])
    definition = build_tool_definitions(AgentDependencies(None, {tool["name"]: tool}, 8))[0]
    assert 'Luôn gọi với arguments {}' not in definition.description
    assert validate_catalog_arguments(tool, {"query": "Tuấn"}) == {"query": "Tuấn"}


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
    assert agent.kwargs["model_settings"] == {
        "temperature": 0.6, "top_p": 0.95, "seed": 7,
        "extra_body": {"top_k": 20, "min_p": 0, "chat_template_kwargs": {"enable_thinking": True}},
    }


def test_history_removes_thinking_without_mutating_original():
    from dataclasses import dataclass
    from lifemate.pydantic_agent import without_thinking
    @dataclass
    class Response:
        parts: list
        kind: str = 'response'
    thought = types.SimpleNamespace(part_kind='thinking', content='reasoning')
    tool = types.SimpleNamespace(part_kind='tool-call', tool_name='contacts_search')
    text = types.SimpleNamespace(part_kind='text', content='answer')
    original = Response([thought, tool, text])
    cleaned = without_thinking([original])
    assert cleaned[0].parts == [tool, text]
    assert original.parts == [thought, tool, text]


def test_iter_runner_preserves_same_response_calls_and_stops_for_user():
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


@pytest.mark.parametrize('first_calls', [
    [{'name': 'calendar.create_event', 'kind': 'write'}],
    [{'name': 'bill_payment.pay', 'kind': 'write', 'result': {'done': False}}],
    [{'name': 'contacts.search', 'kind': 'read'}, {'name': 'alarm.create', 'kind': 'write'}],
    [{'name': 'sys.other', 'kind': 'meta'}],
    [],
])
def test_iter_continues_until_agent_finishes(first_calls):
    End = type('End', (), {})
    class FakeRun:
        def __init__(self, deps):
            self.deps, self.steps = deps, 0
            self.next_node = object()
            self.result = None
        async def next(self, node):
            self.steps += 1
            if self.steps == 1:
                self.deps.calls.extend(first_calls)
                return object()
            self.deps.calls.append({'name': 'sms.send', 'kind': 'write'})
            self.result = 'finished'
            return End()
    class FakeAgent:
        @asynccontextmanager
        async def iter(self, prompt, *, deps, usage_limits, **kwargs):
            assert usage_limits.request_limit == 10
            self.run = FakeRun(deps)
            yield self.run
    deps = AgentDependencies(object(), {}, max_steps=10)
    agent = FakeAgent()
    assert run_agent(agent, deps, 'request') == 'finished'
    assert agent.run.steps == 2
    assert deps.calls[-1]['name'] == 'sms.send'


def test_iter_keeps_usage_limit_error_without_synthetic_calls():
    class FakeRun:
        next_node = object()
        result = None
        async def next(self, node):
            raise RuntimeError('request_limit=10 exceeded')
    class FakeAgent:
        @asynccontextmanager
        async def iter(self, prompt, **kwargs):
            assert kwargs['usage_limits'].request_limit == 10
            yield FakeRun()
    deps = AgentDependencies(object(), {}, max_steps=10)
    assert run_agent(FakeAgent(), deps, 'request') is None
    assert deps.error == 'request_limit=10 exceeded'
    assert deps.calls == []
