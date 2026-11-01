from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_agent_batch_keeps_one_loop_and_closes_it_after_batch():
    import asyncio
    from lifemate.pydantic_agent import agent_event_loop, run_agent_coroutine
    loops = []
    async def request():
        loop = asyncio.get_running_loop()
        if loops:
            assert loops[0] is loop
            assert not loops[0].is_closed()
        loops.append(loop)
        return 'ok'
    with agent_event_loop():
        assert run_agent_coroutine(request()) == 'ok'
        assert run_agent_coroutine(request()) == 'ok'
    assert loops[0].is_closed()


def load_smoke_module():
    path = Path(__file__).parents[1] / 'scripts' / 'smoke_e2e_langsmith.py'
    spec = importlib.util.spec_from_file_location('smoke_test_module', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_debug_client_sends_synchronously_and_does_not_sample(monkeypatch):
    module = load_smoke_module()
    captured = {}
    def client(**kwargs):
        captured.update(kwargs)
        return 'client'
    monkeypatch.setattr(module, 'Client', client)
    assert module.create_trace_client('secret') == 'client'
    assert captured['auto_batch_tracing'] is False
    assert captured['tracing_sampling_rate'] == 1.0


def test_span_times_and_dotted_order_follow_execution_even_with_clock_ties(monkeypatch):
    from datetime import datetime, timezone
    import lifemate.langsmith_e2e as tracing
    fixed = datetime(2026, 11, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(tracing, '_now', lambda: fixed)
    client = FakeClient()
    tracer = tracing.LangSmithE2ETracer(client, 'project', 'root', 'root-order')
    for name, kind in [('llm.first', 'llm'), ('tool.read', 'tool'), ('llm.second', 'llm'), ('tool.write', 'tool')]:
        tracer.trace(name, kind, {}, lambda: None)
    times = [r['start_time'] for r in client.created]
    assert times == sorted(set(times))
    assert [r['name'] for r in sorted(client.created, key=lambda r: r['dotted_order'])] == [
        'llm.first', 'tool.read', 'llm.second', 'tool.write']
    for run in client.created:
        assert run['dotted_order'].split('.')[-1].startswith(run['start_time'].strftime('%Y%m%dT%H%M%S%fZ'))
    for _, update in client.updated:
        assert update['trace_id'] == 'root'
        assert update['dotted_order']


def test_nested_traces_use_agent_parent_and_restore_context():
    from lifemate.langsmith_e2e import LangSmithE2ETracer
    client = FakeClient()
    tracer = LangSmithE2ETracer(client, 'project', 'root', 'root-order')
    tracer.trace('agent', 'chain', {}, lambda: tracer.trace('tool', 'tool', {}, lambda: 'ok'))
    agent, tool = client.created
    assert tool['parent_run_id'] == agent['id']
    assert tool['dotted_order'].startswith(agent['dotted_order'] + '.')
    tracer.trace('next', 'chain', {}, lambda: None)
    assert client.created[-1]['parent_run_id'] == 'root'


@pytest.mark.parametrize('failed', [False, True])
def test_sdk_patch_preserves_nested_span_parent(monkeypatch, failed):
    from uuid import uuid4
    from langsmith import Client
    from lifemate.langsmith_e2e import LangSmithE2ETracer

    patches = []
    monkeypatch.setattr(Client, 'create_run', lambda self, **kwargs: None)
    monkeypatch.setattr(Client, '_update_run', lambda self, data, **kwargs: patches.append(data))
    client = Client(api_key='test-key', auto_batch_tracing=False, tracing_sampling_rate=1.0)
    root_id = str(uuid4())
    tracer = LangSmithE2ETracer(client, 'project', root_id, 'root-order')
    agent_id, agent_order = tracer.start('agent', 'chain', {})
    token = tracer._parent.set((agent_id, agent_order))
    child_id, child_order = tracer.start('tool', 'tool', {})
    tracer._parent.reset(token)
    # Finishing after context restoration must still use the original parent.
    tracer.finish(child_id, outputs={'ok': True},
                  error=RuntimeError('tool failed') if failed else None)
    tracer.finish(agent_id, outputs={})
    assert str(patches[0]['parent_run_id']) == agent_id
    assert str(patches[0]['trace_id']) == root_id
    assert patches[0]['dotted_order'] == child_order
    assert str(patches[1]['parent_run_id']) == root_id


def test_async_model_trace_records_messages_usage_and_errors():
    import asyncio
    from dataclasses import dataclass
    from lifemate.langsmith_e2e import LangSmithE2ETracer
    @dataclass
    class Response:
        parts: list
        usage: dict
    client = FakeClient()
    tracer = LangSmithE2ETracer(client, 'project', 'root', 'root-order')
    response = Response([{'text': 'hello'}], {'input_tokens': 4, 'output_tokens': 2})
    async def request():
        return response
    assert asyncio.run(tracer.trace_model('qwen', {'messages': []}, request)) is response
    payload = client.updated[-1][1]
    assert payload['outputs']['response']['parts'] == [{'text': 'hello'}]
    assert payload['outputs']['usage_metadata']['total_tokens'] == 6
    async def broken():
        raise RuntimeError('provider failed')
    with pytest.raises(RuntimeError, match='provider failed'):
        asyncio.run(tracer.trace_model('qwen', {}, broken))
    assert 'provider failed' in client.updated[-1][1]['error']


def test_model_wrapper_forwards_requests_and_records_each_turn(monkeypatch):
    import asyncio
    import sys
    from types import SimpleNamespace
    from lifemate.langsmith_e2e import LangSmithE2ETracer, tracing_model
    class Wrapper:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.model_name = wrapped.model_name
    monkeypatch.setitem(sys.modules, 'pydantic_ai.models.wrapper', SimpleNamespace(WrapperModel=Wrapper))
    class Model:
        model_name = 'qwen'
        async def request(self, messages, settings, parameters):
            assert settings == {'temperature': 0}
            return {'messages_seen': len(messages)}
    client = FakeClient()
    tracer = LangSmithE2ETracer(client, 'project', 'root', 'root-order')
    model = tracing_model(Model(), tracer)
    for count in (1, 3):
        messages = [{'content': str(i)} for i in range(count)]
        result = asyncio.run(model.request(messages, {'temperature': 0}, {}))
        assert result == {'messages_seen': count}
        assert client.created[-1]['inputs']['messages'] == messages
    assert len(client.created) == 2


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
    project, examples = module.prepare_experiment(client, [{'id': 'a', 'audio_text': 'hello', 'label': {'tool_calls': []}}],
        'dataset-name', 'test-run', {'input_mode': 'reference_text'},
        references={'a': {'tool_calls': [], 'state_hash': 'gold'}})
    assert client.project['reference_dataset_id'] == 'dataset'
    assert client.example['inputs']['audio_text'] == 'hello'
    assert 'label' not in client.example['inputs']
    assert client.example['outputs'] == {'tool_calls': [], 'state_hash': 'gold'}
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
        assert 'label' not in sample
        assert kwargs['asr'] is None
        assert runner.transcript(sample, kwargs['asr']) == 'label text'
        return {'id': 'a', 'tool_calls': [], 'state_hash': 'hash'}
    runner.run_sample = run_sample
    args = SimpleNamespace(split='train', asr_backend='gipformer', llm_model_name='qwen',
        use_reference_text=True, example_ids={'a': 'example'}, root=tmp_path, max_steps=8, seed=0)
    client = FakeClient()
    result = module._run_one_sample({'id': 'a', 'audio_text': 'label text', 'label': {'tool_calls': []}}, args=args,
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
        assert kwargs.get('trace_id') is not None, 'SDK sampling requires trace_id on updates'
        assert kwargs.get('dotted_order'), 'Updates must retain trace hierarchy'
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


def test_experiment_selects_only_ids_from_file(tmp_path):
    module = load_smoke_module()
    ids = tmp_path / 'ids.txt'
    ids.write_text('train_0002\n\ntrain_0000\ntrain_0002\n', encoding='utf-8')
    samples = [{'id': f'train_{index:04d}'} for index in range(4)]
    assert module.select_samples(samples, sample_ids_file=ids) == [samples[0], samples[2]]


def test_experiment_rejects_unknown_or_empty_id_file(tmp_path):
    module = load_smoke_module()
    ids = tmp_path / 'ids.txt'
    ids.write_text('train_missing\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='train_missing'):
        module.select_samples([{'id': 'train_0000'}], sample_ids_file=ids)
    ids.write_text('\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='empty'):
        module.select_samples([{'id': 'train_0000'}], sample_ids_file=ids)
