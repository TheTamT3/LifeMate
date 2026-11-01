from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_smoke_module():
    path = Path(__file__).parents[1] / 'scripts' / 'smoke_e2e_langsmith.py'
    spec = importlib.util.spec_from_file_location('smoke_test_module', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_mode_skips_asr_and_requires_train_text():
    module = load_smoke_module()
    assert module.prepare_asr([{'id': 'a', 'audio_text': 'hello'}], 'train', True, None) is None
    with pytest.raises(ValueError, match='audio_text'):
        module.prepare_asr([{'id': 'a'}], 'train', True, None)
    with pytest.raises(ValueError, match='train'):
        module.prepare_asr([{'audio_text': 'hello'}], 'public_test', True, None)


def test_experiment_links_dataset_examples_and_root_run():
    from types import SimpleNamespace
    from langsmith.utils import LangSmithNotFoundError
    module = load_smoke_module()
    class Client(FakeClient):
        def read_dataset(self, **kwargs):
            raise LangSmithNotFoundError('missing')
        def create_dataset(self, **kwargs):
            return SimpleNamespace(id='dataset')
        def read_example(self, example_id):
            raise LangSmithNotFoundError('missing')
        def create_example(self, **kwargs):
            self.example = kwargs
        def create_project(self, **kwargs):
            self.project = kwargs
            return SimpleNamespace(id='experiment', name='test-run')
    client = Client()
    project, examples = module.prepare_experiment(client, [{'id': 'a', 'audio_text': 'hello'}],
        'dataset-name', 'test-run', {'input_mode': 'reference_text'})
    assert client.project['reference_dataset_id'] == 'dataset'
    assert client.example['inputs']['audio_text'] == 'hello'
    assert examples['a'] == client.example['example_id']
    module._create_root_run(client, project.name, {'id': 'a'}, 'train', 'reference_text', 'qwen', examples['a'])
    assert client.created[0]['reference_example_id'] == examples['a']


def test_experiment_reuses_existing_examples():
    from types import SimpleNamespace
    module = load_smoke_module()
    class Client:
        def read_dataset(self, **kwargs):
            return SimpleNamespace(id='existing-dataset')
        def read_example(self, example_id):
            return SimpleNamespace(id=example_id)
        def create_project(self, **kwargs):
            return SimpleNamespace(name=kwargs['project_name'])
        def create_example(self, **kwargs):
            pytest.fail('Existing examples must be reused')
    samples = [{'id': 'a', 'audio_text': 'hello'}]
    _, first = module.prepare_experiment(Client(), samples, 'dataset', 'run1', {})
    _, second = module.prepare_experiment(Client(), samples, 'dataset', 'run2', {})
    assert first == second


def test_reference_run_uses_text_and_restores_runner(tmp_path):
    from types import SimpleNamespace
    from lifemate.asr import transcript
    module = load_smoke_module()
    def run_agent(*args, **kwargs):
        return None
    runner = SimpleNamespace(_tool_env=lambda *a: None, transcript=transcript, run_agent=run_agent)
    def run_sample(sample, **kwargs):
        assert kwargs['asr'] is None
        assert runner.transcript(sample, kwargs['asr']) == 'label text'
        return {'id': 'a', 'tool_calls': [], 'state_hash': 'hash'}
    runner.run_sample = run_sample
    args = SimpleNamespace(split='train', asr_backend='gipformer', llm_model_name='qwen',
        use_reference_text=True, example_ids={'a': 'example'}, root=tmp_path, max_steps=8, seed=0)
    client = FakeClient()
    result = module._run_one_sample({'id': 'a', 'audio_text': 'label text'}, args=args,
        catalog={}, runner=runner, llm=None, asr=None, client=client, project='experiment')
    assert result['state_hash'] == 'hash'
    assert client.created[1]['name'] == 'input.reference_text'
    assert runner.transcript is transcript
    assert runner.run_agent is run_agent


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


@pytest.mark.parametrize("result", ["recognized text", [1, 2], None, 42, True])
def test_trace_wraps_non_object_outputs_without_changing_result(result):
    from lifemate.langsmith_e2e import LangSmithE2ETracer

    client = FakeClient()
    tracer = LangSmithE2ETracer(client, "project", "root", "root-order")
    assert tracer.trace("asr", "chain", {}, lambda: result) is result
    assert client.updated[0][1]["outputs"] == {"output": result}


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
