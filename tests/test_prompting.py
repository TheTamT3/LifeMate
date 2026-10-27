from lifemate.prompting import build_prompt


def test_prompt_contains_request_history_tools_observations_and_rules():
    prompt = build_prompt(
        {"context": {"installed_apps": {"weather": {"tools": ["weather.get_current"]}}, "x": 1}, "history": []},
        "Hôm nay mưa không?",
        [{"name": "weather.get_current", "kind": "read", "description": "current", "parameters": {"type": "object"}}],
        [{"ok": True}],
    )
    assert "Hôm nay mưa không?" in prompt
    assert "weather.get_current" in prompt
    assert "previous_tool_results" in prompt
    assert "Return only a JSON array" in prompt
    assert "Few-shot" in prompt
