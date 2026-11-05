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


def test_system_prompt_adds_only_derived_calendar_facts_not_label_or_state():
    sample = {
        "context": {"current_time": "2026-11-03T23:30:00+07:00", "timezone": "Asia/Ho_Chi_Minh"},
        "label": {"secret_label": "gold-only"},
        "state": {"secret_state": "state-only"},
    }
    system = _build_system_prompt(sample)
    assert "Mốc lịch suy ra từ context" in system
    assert '"tomorrow": "2026-11-04"' in system
    calendar_fragment = system.split('"calendar": ', 1)[1]
    days = json.loads(calendar_fragment[: calendar_fragment.index("]") + 1])
    assert days[3] == {"date": "2026-11-05", "weekday_vi": "thứ năm"}
    assert len(days) == 14
    assert "gold-only" not in system
    assert "state-only" not in system


def test_system_prompt_omits_calendar_facts_without_aware_anchor():
    system = _build_system_prompt({"context": {"current_time": "2026-11-03T23:30:00"}})
    assert "Mốc lịch suy ra từ context" not in system


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
    assert mapping == {
        "alarm.list": "alarm_list",
        "alarm.delete": "alarm_delete",
    }
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
