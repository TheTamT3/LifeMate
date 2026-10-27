import sys
import types

from lifemate.runner import run_sample


class FakeEnv:
    instances = []

    def __init__(self, split, sample_id, root):
        self.calls = []
        self.results = []
        FakeEnv.instances.append(self)

    def call(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        result = {"ok": True, "id": "evt_1"} if name.endswith("list") else {"ok": True}
        self.results.append(result)
        return result

    def get_tool_calls(self):
        return self.calls

    def get_state_hash(self):
        return "hash-from-env"


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def generate(self, prompt):
        return next(self.outputs)


def install_fake_env(monkeypatch):
    module = types.ModuleType("zaic_tools")
    module.ToolEnv = FakeEnv
    monkeypatch.setitem(sys.modules, "zaic_tools", module)


def test_noop_returns_env_hash_and_one_environment(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    FakeEnv.instances.clear()
    sample = {"id": "s1", "audio_text": "không làm gì", "context": {"installed_apps": {}}}
    result = run_sample(sample, "train", tmp_path, {}, FakeLLM(["[]"]))
    assert result == {"id": "s1", "tool_calls": [], "state_hash": "hash-from-env"}
    assert len(FakeEnv.instances) == 1


def test_unavailable_tool_is_not_executed(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    sample = {"id": "s2", "audio_text": "x", "context": {"installed_apps": {"a": {"tools": ["x.read"]}}}}
    result = run_sample(sample, "train", tmp_path, {"x.read": {"name": "x.read", "kind": "read"}}, FakeLLM(['[{"name":"bad.write","arguments":{}}]']))
    assert result["tool_calls"] == []


def test_read_then_action_can_use_second_model_step(monkeypatch, tmp_path):
    install_fake_env(monkeypatch)
    sample = {"id": "s3", "audio_text": "đổi lịch", "context": {"installed_apps": {"a": {"tools": ["calendar.list", "calendar.update"]}}}}
    catalog = {
        "calendar.list": {"name": "calendar.list", "kind": "read"},
        "calendar.update": {"name": "calendar.update", "kind": "write"},
    }
    llm = FakeLLM([
        '[{"name":"calendar.list","arguments":{}}]',
        '[{"name":"calendar.update","arguments":{"event_id":"evt_1"}}]',
    ])
    result = run_sample(sample, "train", tmp_path, catalog, llm)
    assert [item["name"] for item in result["tool_calls"]] == ["calendar.list", "calendar.update"]
