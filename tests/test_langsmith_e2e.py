from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


class FakeClient:
    def __init__(self) -> None:
        self.created = []
        self.updated = []

    def create_run(self, **kwargs):
        self.created.append(kwargs)

    def update_run(self, run_id, **kwargs):
        self.updated.append((run_id, kwargs))

    def flush(self):
        return None


class FakeEnv:
    def __init__(self) -> None:
        self.calls = []

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        return {"ok": True, "name": name}

    def get_tool_calls(self):
        return [{"name": name, "arguments": args} for name, args in self.calls]

    def get_state_hash(self):
        return "hash"


def test_tracing_tool_env_records_successful_call():
    from lifemate.langsmith_e2e import LangSmithE2ETracer, TracingToolEnv

    client = FakeClient()
    tracer = LangSmithE2ETracer(client, "project", root_run_id="root", root_dotted_order="root-order")
    env = TracingToolEnv(FakeEnv(), tracer)

    assert env.call("weather.get_forecast", {"city": "Hanoi"}) == {"ok": True, "name": "weather.get_forecast"}
    assert env.get_state_hash() == "hash"
    assert client.created[0]["name"] == "tool.weather.get_forecast"
    assert client.updated[0][1]["outputs"]["ok"] is True


def test_tracing_tool_env_records_and_reraises_tool_error():
    from lifemate.langsmith_e2e import LangSmithE2ETracer, TracingToolEnv

    class BrokenEnv(FakeEnv):
        def call(self, name, arguments):
            raise RuntimeError("tool failed")

    client = FakeClient()
    tracer = LangSmithE2ETracer(client, "project", root_run_id="root", root_dotted_order="root-order")
    env = TracingToolEnv(BrokenEnv(), tracer)

    with pytest.raises(RuntimeError, match="tool failed"):
        env.call("calendar.list_events", {})

    assert client.updated[0][1]["error"] == "RuntimeError: tool failed"


def test_smoke_cli_rejects_missing_langsmith_environment(monkeypatch, tmp_path: Path):
    script_path = Path(__file__).parents[1] / "scripts" / "smoke_e2e_langsmith.py"
    spec = importlib.util.spec_from_file_location("smoke_e2e_langsmith", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    with pytest.raises(SystemExit, match="LANGSMITH_API_KEY, LANGSMITH_PROJECT"):
        module.require_langsmith_environment()


def test_experiment_selects_requested_number_of_samples():
    script_path = Path(__file__).parents[1] / "scripts" / "smoke_e2e_langsmith.py"
    spec = importlib.util.spec_from_file_location("smoke_e2e_langsmith", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    samples = [{"id": f"train_{index:04d}"} for index in range(5)]
    assert [item["id"] for item in module.select_samples(samples, limit=3)] == [
        "train_0000",
        "train_0001",
        "train_0002",
    ]
