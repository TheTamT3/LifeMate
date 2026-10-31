import json

from lifemate.runner import (
    _build_agent_prompt,
    _build_system_prompt,
    _history_records,
)
from lifemate.pydantic_agent import tool_name_map


def test_prompt_separates_system_context_from_current_user_request():
    sample = {
        "audio_text": "Bật đèn phòng khách",
        "context": {
            "city": "Đà Nẵng",
            "installed_apps": {"smart_home": {"tools": ["smart_home.light_set"]}},
        },
        "history": [],
    }
    system = _build_system_prompt(sample)
    assert "Bật đèn phòng khách" not in system
    assert "installed_apps" not in system
    assert "Đà Nẵng" in system
    assert _build_agent_prompt(sample, sample["audio_text"], []) == sample["audio_text"]


def test_history_maps_official_tool_names_to_wire_names_and_tool_results():
    tools = [
        {"name": "alarm.list", "kind": "read"},
        {"name": "alarm.delete", "kind": "write"},
    ]
    sample = {
        "history": [
            {"role": "user", "audio_text": "Có báo thức nào không?"},
            {
                "role": "assistant",
                "text": "Có một báo thức.",
                "tool_calls": [{"name": "alarm.list", "arguments": {}}],
                "tool_results": [{"ok": True, "alarms": [{"id": "alm_1"}]}],
            },
        ]
    }
    mapping = tool_name_map(tools)
    records = _history_records(sample, mapping)
    assert records[0] == {"role": "user", "content": "Có báo thức nào không?"}
    assert records[1]["role"] == "assistant"
    call = records[1]["tool_calls"][0]
    assert call["name"] == mapping["alarm.list"]
    assert call["tool_call_id"] == "history_1_call_0"
    assert records[2] == {
        "role": "tool",
        "name": mapping["alarm.list"],
        "tool_call_id": "history_1_call_0",
        "content": json.dumps({"ok": True, "alarms": [{"id": "alm_1"}]}, ensure_ascii=False),
    }
