import sys
import types

import pytest
from pydantic import ValidationError

from lifemate.pydantic_agent import (
    AgentDependencies,
    build_tool_definitions,
    catalog_argument_model,
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


def test_tool_factory_keeps_description_and_calls_official_name(monkeypatch):
    class FakeTool:
        def __init__(self, function, name, description, args_validator):
            self.function = function
            self.name = name
            self.description = description
            self.args_validator = args_validator

        @classmethod
        def from_schema(cls, function, name, description, json_schema, takes_ctx, args_validator, sequential):
            return cls(function, name, description, args_validator)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    calls = []

    class FakeEnv:
        def call(self, name, arguments):
            calls.append((name, arguments))
            return {"ok": True}

    tool = _tool(type="object", properties={"title": {"type": "string"}}, required=["title"])
    definitions = build_tool_definitions(AgentDependencies(FakeEnv(), {tool["name"]: tool}, 8))
    assert len(definitions) == 1
    assert definitions[0].name != tool["name"]
    assert definitions[0].description == tool["description"]
    definitions[0].args_validator(None, {"title": "x"})
    definitions[0].function(None, title="x")
    assert calls == [(tool["name"], {"title": "x"})]
