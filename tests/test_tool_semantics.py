import copy
import json
import sys
import types
from types import SimpleNamespace

from lifemate.pydantic_agent import AgentDependencies, build_tool_definitions, catalog_argument_model
from lifemate.tool_semantics import tool_semantics_note


def test_order_history_note_documents_ignored_limit():
    assert "không áp dụng limit" in tool_semantics_note("food_delivery.order_history")


def test_unknown_tool_has_no_note():
    assert tool_semantics_note("calendar.list_events") == ""


def test_optional_value_notes_match_runtime_defaults():
    assert "giữ nhiệt độ hiện tại" in tool_semantics_note("smart_home.climate_set")
    assert "mức normal" in tool_semantics_note("tasks.add")


def test_argument_semantics_overlays_do_not_mutate_schemas_or_execution(monkeypatch):
    captured = []

    class FakeTool:
        @classmethod
        def from_schema(cls, function, **kwargs):
            captured.append((function, kwargs))
            return kwargs

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Tool=FakeTool))
    catalog_tools = [
        {"name": "ride_hailing.get_ride", "kind": "read", "description": "Trạng thái chuyến hiện tại",
         "parameters": {"type": "object", "properties": {"ride_id": {"type": "string", "description": "ID chuyến xe"}}, "required": []}},
        {"name": "bill_payment.pay", "kind": "write", "description": "Thanh toán hóa đơn",
         "parameters": {"type": "object", "properties": {"bill_id": {"type": "string"}, "source": {"type": "string", "enum": ["ewallet", "bank"]}}, "required": ["bill_id", "source"]}},
        {"name": "calendar.update_event", "kind": "write", "description": "Cập nhật sự kiện",
         "parameters": {"type": "object", "properties": {"event_id": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}, "required": ["event_id"]}},
    ]
    original = copy.deepcopy(catalog_tools)

    class FakeEnv:
        def __init__(self):
            self.received = []

        def call(self, name, arguments):
            self.received.append((name, arguments))
            return {"ok": True, "tool": name}

    env = FakeEnv()
    deps = AgentDependencies(env=env, tools_by_name={tool["name"]: tool for tool in catalog_tools}, max_steps=10)
    definitions = build_tool_definitions(deps)
    assert len(definitions) == 3
    descriptions = {item[1]["name"]: item[1]["description"] for item in captured}
    assert "không truyền ride_id" in descriptions["ride_hailing_get_ride"].casefold()
    assert "toàn bộ hóa đơn" in descriptions["bill_payment_pay"].casefold()
    assert "nếu bỏ end" in descriptions["calendar_update_event"].casefold()
    arguments = [({},), ({"bill_id": "bill_1", "source": "ewallet"},), ({"event_id": "evt_1", "start": "2026-11-06T10:00:00+07:00"},)]
    for (function, _), (kwargs,) in zip(captured, arguments):
        function(SimpleNamespace(deps=deps), **kwargs)
    assert env.received == [
        ("ride_hailing.get_ride", {}),
        ("bill_payment.pay", {"bill_id": "bill_1", "source": "ewallet"}),
        ("calendar.update_event", {"event_id": "evt_1", "start": "2026-11-06T10:00:00+07:00"}),
    ]
    assert catalog_tools == original
    assert [item[1]["json_schema"] for item in captured] == [
        catalog_argument_model(tool).model_json_schema() for tool in catalog_tools
    ]


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
