import copy
import json
import sys
import types
from types import SimpleNamespace

from lifemate.pydantic_agent import AgentDependencies, build_tool_definitions
from lifemate.tool_semantics import tool_semantics_note


def test_order_history_note_documents_ignored_limit():
    assert "không áp dụng limit" in tool_semantics_note("food_delivery.order_history")


def test_unknown_tool_has_no_note():
    assert tool_semantics_note("calendar.list_events") == ""


def test_optional_value_notes_match_runtime_defaults():
    assert "giữ nhiệt độ hiện tại" in tool_semantics_note("smart_home.climate_set")
    assert "mức normal" in tool_semantics_note("tasks.add")


def test_description_overlay_preserves_catalog_and_arguments(monkeypatch):
    captured = []

    class FakeTool:
        @classmethod
        def from_schema(cls, function, **kwargs):
            captured.append((function, kwargs))
            return kwargs

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    catalog_tool = {
        "name": "food_delivery.order_history",
        "description": "Lịch sử đơn hàng",
        "kind": "read",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []},
    }
    original = copy.deepcopy(catalog_tool)
    class FakeEnv:
        def __init__(self):
            self.received = []

        def call(self, name, arguments):
            self.received.append((name, arguments))
            return {"ok": True}

    env = FakeEnv()
    deps = AgentDependencies(env=env, tools_by_name={catalog_tool["name"]: catalog_tool}, max_steps=10)
    definitions = build_tool_definitions(deps)
    assert len(definitions) == 1
    assert "không áp dụng limit" in captured[0][1]["description"]
    assert captured[0][1]["json_schema"]["properties"] == {
        "limit": {"default": None, "title": "Limit", "type": "integer"}
    }
    captured[0][0](SimpleNamespace(deps=deps), limit=1)
    assert env.received == [("food_delivery.order_history", {"limit": 1})]
    assert catalog_tool == original
