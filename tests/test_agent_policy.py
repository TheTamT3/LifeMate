from lifemate.agent_policy import BASE_POLICY, CONDITION_POLICY, EVIDENCE_POLICY, INTENT_POLICY, QUERY_POLICY, TIME_POLICY, agent_instructions


def test_agent_instructions_preserve_base_and_append_query_policy_once():
    text = agent_instructions()
    assert text.startswith(BASE_POLICY)
    assert text.count(QUERY_POLICY) == 1
    assert text.index(BASE_POLICY) < text.index(QUERY_POLICY)


def test_policy_does_not_add_case_ids_or_domain_specific_rules():
    text = agent_instructions()
    assert "train_" not in text
    assert "bill_payment" not in text
    assert "food_delivery" not in text


def test_condition_policy_is_general_and_composed_after_query_policy():
    text = agent_instructions()
    assert CONDITION_POLICY
    assert text.index(QUERY_POLICY) < text.index(CONDITION_POLICY)
    assert "điều kiện nằm trong nội dung" in CONDITION_POLICY.casefold()
    assert "weather" not in CONDITION_POLICY


def test_condition_policy_waits_for_results_only_when_a_later_call_depends_on_them():
    policy = CONDITION_POLICY.casefold()
    assert "chỉ có sau kết quả call trước" in policy
    assert "chờ kết quả đó rồi mới tạo call phụ thuộc" in policy
    assert "các call độc lập vẫn có thể được tạo cùng lượt" in policy
    assert "không bịa dữ kiện" in policy


def test_condition_examples_are_manifested_and_user_text_stays_literal():
    import json
    from pathlib import Path
    from lifemate.runner import _build_agent_prompt, _history_records

    cases = json.loads(Path("tests/fixtures/mechanism_cases.json").read_text(encoding="utf-8"))
    ids = {case["sample_id"] for case in cases if case["cluster"] == "R04"}
    assert {"train_0533", "train_0190", "train_0107"}.issubset(ids)
    message = 'Gửi nội dung "nếu trời mưa thì ở nhà" cho chị.'
    assert _build_agent_prompt({}, message, []) == message
    history = _history_records({"history": [{"role": "user", "text": message}]}, {})
    assert history == [{"role": "user", "content": message}]


def test_intent_policy_follows_condition_policy_and_mentions_retraction():
    text = agent_instructions()
    assert INTENT_POLICY
    assert text.index(CONDITION_POLICY) < text.index(INTENT_POLICY)
    assert "rút lại" in INTENT_POLICY
    assert "không tự quay lại" in INTENT_POLICY


def test_retraction_history_and_latest_request_are_preserved():
    from lifemate.runner import _build_agent_prompt, _history_records

    history = [
        {"role": "user", "text": "Đặt lịch nhắc uống thuốc mỗi ngày."},
        {"role": "assistant", "tool_calls": [{"name": "reminders.create", "arguments": {"title": "Uống thuốc"}}], "tool_results": [{"ok": True}]},
        {"role": "user", "text": "Thôi khỏi nhắc mỗi ngày, chỉ nhắc hôm nay thôi."},
    ]
    records = _history_records({"history": history}, {"reminders.create": "reminders_create"})
    assert records[0]["content"] == history[0]["text"]
    assert records[-1]["content"] == history[-1]["text"]
    assert records[1]["tool_calls"][0]["tool_call_id"] == records[2]["tool_call_id"]
    latest = "Chỉ hủy lời nhắc ngày mai."
    assert _build_agent_prompt({}, latest, []) == latest


def test_time_policy_follows_intent_policy_and_uses_context_as_anchor():
    text = agent_instructions()
    assert TIME_POLICY
    assert text.index(INTENT_POLICY) < text.index(TIME_POLICY)
    assert "thời gian trong context" in TIME_POLICY.casefold()
    assert "múi giờ" in TIME_POLICY


def test_time_policy_preserves_request_dates_and_resolves_clock_and_anchor_roles():
    assert "yêu cầu còn hiệu lực" in TIME_POLICY
    assert "lời sửa hoặc căn cứ mới" in TIME_POLICY
    assert "giờ, phút và buổi" in TIME_POLICY
    assert "thời điểm sự kiện, thời gian di chuyển, giờ nhắc và hạn chót" in TIME_POLICY
    assert "không chọn mốc khác chỉ vì nó xuất hiện gần hơn" in TIME_POLICY


def test_time_policy_preserves_exact_time_offsets_and_deadlines():
    assert "không tự chuyển sang sớm hơn" in TIME_POLICY
    assert "chỉ trừ đúng khoảng thời gian được yêu cầu" in TIME_POLICY
    assert "giữ X giờ là hạn chót" in TIME_POLICY
    assert "người dùng đã giao quyền chọn giờ" in TIME_POLICY


def test_context_and_confirmed_event_time_remain_available_without_rewriting_request():
    import json
    from lifemate.runner import _build_agent_prompt, _history_records, _build_system_prompt

    sample = {
        "context": {"current_time": "2026-11-03T23:30:00+07:00"},
        "history": [
            {"role": "assistant", "tool_calls": [{"name": "calendar.list_events", "arguments": {}}],
             "tool_results": [{"ok": True, "events": [{"id": "evt_1", "start": "2026-11-04T09:00:00+07:00"}]}]},
        ],
    }
    system = _build_system_prompt(sample)
    assert "2026-11-03T23:30:00+07:00" in system
    assert "2026-11-04" in system
    records = _history_records(sample, {"calendar.list_events": "calendar_list_events"})
    assert json.loads(records[-1]["content"])["events"][0]["start"] == "2026-11-04T09:00:00+07:00"
    explicit = "Đặt lịch lúc 23:30 ngày 20/12/2027."
    assert _build_agent_prompt(sample, explicit, []) == explicit


def test_updated_event_anchor_is_preserved_in_history_after_update_tool():
    import json
    from lifemate.runner import _history_records

    updated = "2026-11-06T18:30:00+07:00"
    sample = {"history": [{
        "role": "assistant",
        "tool_calls": [{"name": "calendar.update_event", "arguments": {"event_id": "evt_1", "start": updated}}],
        "tool_results": [{"ok": True, "item": {"id": "evt_1", "start": updated}}],
    }]}
    records = _history_records(sample, {"calendar.update_event": "calendar_update_event"})
    assert json.loads(records[-1]["content"])["item"]["start"] == updated


def test_time_policy_cases_and_controls_are_in_manifest():
    import json
    from pathlib import Path
    cases = json.loads(Path("tests/fixtures/mechanism_cases.json").read_text(encoding="utf-8"))
    ids = {case["sample_id"] for case in cases if case["cluster"] == "R06"}
    assert {"train_0546", "train_0124", "train_0381", "train_0247", "train_0033"}.issubset(ids)


def test_evidence_policy_follows_time_and_covers_grounding_optional_values_and_results():
    text = agent_instructions()
    assert EVIDENCE_POLICY
    assert text.index(TIME_POLICY) < text.index(EVIDENCE_POLICY)
    for phrase in ("ví dụ trong schema", "tham số optional", "đã gọi tool không đồng nghĩa đã thành công"):
        assert phrase in EVIDENCE_POLICY.casefold()


def test_evidence_policy_preserves_entity_identity_facts_and_delegated_choice():
    assert "đúng loại đối tượng" in EVIDENCE_POLICY
    assert "thứ tự kết quả không phải tiêu chí chọn" in EVIDENCE_POLICY
    assert "người dùng cho phép chọn tùy ý" in EVIDENCE_POLICY
    assert "giữ nguyên các thông tin đã xác nhận" in EVIDENCE_POLICY
    assert "không biến thông tin chưa rõ thành chi tiết cụ thể" in EVIDENCE_POLICY
    assert "phân biệt số lượng, độ dài, đơn giá, hệ số và tổng" in EVIDENCE_POLICY.casefold()
    assert "khi thiếu dữ kiện cần thiết" in EVIDENCE_POLICY.casefold()
    assert "người dùng đã giao quyền chọn giá trị" in EVIDENCE_POLICY
    assert "chỉ vì có hạn chót" in EVIDENCE_POLICY


def test_evidence_cases_cover_tool_choice_grounding_and_literal_recipients():
    import json
    from pathlib import Path
    cases = json.loads(Path("tests/fixtures/mechanism_cases.json").read_text(encoding="utf-8"))
    by_cluster = {}
    for case in cases:
        by_cluster.setdefault(case["cluster"], set()).add(case["sample_id"])
    assert {"train_0088", "train_0817", "train_1141"}.issubset(by_cluster["R02"])
    assert {"train_0116", "train_1292"}.issubset(by_cluster["R03"])
    assert "train_1449" in by_cluster["R07"]
    assert {"train_0681"}.issubset(by_cluster["R08"])
    assert {"train_0643", "train_1123", "train_0103"}.issubset(by_cluster["R09"])


def test_build_agent_uses_composed_policy(monkeypatch):
    import sys
    import types
    from lifemate import pydantic_agent

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Agent=FakeAgent))
    monkeypatch.setattr(pydantic_agent, "_normalizing_model", lambda model, deps: model)
    monkeypatch.setattr(pydantic_agent, "build_tool_definitions", lambda deps: [])
    pydantic_agent.build_agent(object(), pydantic_agent.AgentDependencies(object(), {}, max_steps=10))
    assert captured["instructions"] == agent_instructions()
