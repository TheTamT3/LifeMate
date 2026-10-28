from pathlib import Path

from lifemate.runner import run_sample


class Env:
    def __init__(self, split, sample_id, root):
        self.calls = []

    def call(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        return {"ok": True}

    def get_tool_calls(self):
        return self.calls

    def get_state_hash(self):
        return "stable-hash"


class Agent:
    def run_sync(self, prompt, *, deps, usage_limits, model_settings):
        deps.env.call("weather.get_current", {})


def test_runner_output_is_deterministic_and_hash_is_environment_value(monkeypatch, tmp_path):
    import sys
    import types

    module = types.ModuleType("zaic_tools")
    module.ToolEnv = Env
    monkeypatch.setitem(sys.modules, "zaic_tools", module)
    monkeypatch.setattr("lifemate.runner.build_agent", lambda model, deps: Agent())
    sample = {"id": "s", "audio_text": "thời tiết", "context": {"installed_apps": {"w": {"tools": ["weather.get_current"]}}}}
    catalog = {"weather.get_current": {"name": "weather.get_current", "kind": "write"}}
    first = run_sample(sample, "train", tmp_path, catalog, object())
    second = run_sample(sample, "train", tmp_path, catalog, object())
    assert first == second
    assert first["state_hash"] == "stable-hash"


def test_runner_source_does_not_read_state_json():
    source = Path("src/lifemate/runner.py").read_text(encoding="utf-8")
    assert "state.json" not in source
