import sys
import types

from lifemate.runner import run_sample


class FakeEnv:
    instances = []

    def __init__(self, split, sample_id, root):
        self.calls = []
        FakeEnv.instances.append(self)

    def call(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        return {"ok": True, "id": "evt_1"}

    def get_tool_calls(self):
        return self.calls

    def get_state_hash(self):
        return "hash-from-env"


class FakeAgent:
    def __init__(self, actions):
        self.actions = actions

    def run_sync(self, prompt, *, deps, usage_limits, model_settings):
        for name, arguments in self.actions:
            deps.env.call(name, arguments)


def install_fake_env(monkeypatch):
    module = types.ModuleType("zaic_tools")
    module.ToolEnv = FakeEnv
    monkeypatch.setitem(sys.modules, "zaic_tools", module)


def install_fake_agent(monkeypatch, actions):
    monkeypatch.setattr("lifemate.runner.build_agent", lambda model, deps: FakeAgent(actions))


def test_noop_returns_env_hash_and_one_environment(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    install_fake_agent(monkeypatch, [])
    FakeEnv.instances.clear()
    sample = {"id": "s1", "audio_text": "không làm gì", "context": {"installed_apps": {}}}
    result = run_sample(sample, "train", tmp_path, {}, object())
    assert result == {"id": "s1", "tool_calls": [], "state_hash": "hash-from-env"}
    assert len(FakeEnv.instances) == 1


def test_unavailable_tool_is_not_executed(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    install_fake_agent(monkeypatch, [])
    sample = {"id": "s2", "audio_text": "x", "context": {"installed_apps": {"a": {"tools": ["x.read"]}}}}
    result = run_sample(sample, "train", tmp_path, {"x.read": {"name": "x.read", "kind": "read"}}, object())
    assert result["tool_calls"] == []


def test_read_then_action_can_use_second_model_step(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    install_fake_agent(
        monkeypatch,
        [("calendar.list", {}), ("calendar.update", {"event_id": "evt_1"})],
    )
    sample = {"id": "s3", "audio_text": "đổi lịch", "context": {"installed_apps": {"a": {"tools": ["calendar.list", "calendar.update"]}}}}
    catalog = {
        "calendar.list": {"name": "calendar.list", "kind": "read"},
        "calendar.update": {"name": "calendar.update", "kind": "write"},
    }
    result = run_sample(sample, "train", tmp_path, catalog, object())
    assert [item["name"] for item in result["tool_calls"]] == ["calendar.list", "calendar.update"]


def test_provider_failure_does_not_synthesize_calls(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)

    class FailingAgent:
        def run_sync(self, **_kwargs):
            raise RuntimeError("server unavailable")

    monkeypatch.setattr("lifemate.runner.build_agent", lambda model, deps: FailingAgent())
    sample = {"id": "s4", "audio_text": "x", "context": {"installed_apps": {}}}
    result = run_sample(sample, "train", tmp_path, {}, object())
    assert result["tool_calls"] == []
