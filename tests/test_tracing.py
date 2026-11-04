"""Exercise real LangSmith/PydanticAI nesting with all HTTP mocked."""
import json

import httpx
import pytest
from langsmith import Client
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from lifemate import runner, tracing


@pytest.fixture
def captured_traces(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    monkeypatch.setenv('LANGSMITH_API_KEY', 'test-key-never-exported')
    monkeypatch.setenv('LANGSMITH_PROJECT', 'lifemate-test')
    runs, updates = [], []
    client = Client(api_key='test-key-never-exported', api_url='http://localhost:1',
                    auto_batch_tracing=False, info={'version': 'test'})
    monkeypatch.setattr(Client, 'create_run', lambda self, *args, **kw: runs.append(kw))
    monkeypatch.setattr(Client, 'update_run', lambda self, *args, **kw: updates.append((args, kw)))
    monkeypatch.setattr(tracing, 'get_client', lambda: client)
    return runs, updates


class Environment:
    def __init__(self):
        self.calls = []

    def call(self, name, arguments):
        self.calls.append({'name': name, 'arguments': arguments})
        return {'ok': True}

    def get_tool_calls(self):
        return self.calls

    def get_state_hash(self):
        return 'test-state-hash'


class Speech:
    def transcribe(self, audio):
        return 'Bật đèn'


def test_end_to_end_trace_has_nested_llm_usage_and_tool(captured_traces, monkeypatch, tmp_path):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={
            'id': 'chatcmpl-test', 'object': 'chat.completion', 'created': 1, 'model': 'qwen3-4b',
            'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'call-test', 'type': 'function', 'function': {
                        'name': body['tools'][0]['function']['name'], 'arguments': '{}'}}]}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})

    openai = AsyncOpenAI(base_url='http://localhost:8000/v1', api_key='local',
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    model = OpenAIChatModel('qwen3-4b', provider=OpenAIProvider(openai_client=tracing.wrap_llm_client(openai)))
    monkeypatch.setattr(runner, '_tool_env', lambda *args: Environment())
    sample = {'id': 'sample-test', 'audio': 'test.wav', 'label': 'DO_NOT_TRACE_LABEL',
              'context': {'current_time': '2026-11-16T11:30:00+07:00',
                          'installed_apps': {'home': {'tools': ['home.light_on']}}},
              'history': [{'role': 'user', 'audio': 'previous.wav'},
                          {'role': 'assistant', 'text': 'Đã kiểm tra',
                           'tool_calls': [{'name': 'home.light_on', 'arguments': {}}],
                           'tool_results': [{'ok': True}]}]}
    tool = {'name': 'home.light_on', 'kind': 'write', 'description': 'Bật đèn',
            'parameters': {'type': 'object', 'properties': {}, 'required': []}}
    result = runner.run_sample(sample, 'public_test', tmp_path, {'home.light_on': tool}, model, Speech())
    runs, updates = captured_traces
    by_name = {r['name']: r for r in runs}
    assert {'lifemate.sample', 'tool_env.initialize', 'asr.transcribe', 'agent.prepare',
            'agent.run', 'vllm.chat', 'home.light_on', 'result.serialize'} <= set(by_name)
    assert by_name['vllm.chat']['parent_run_id'] == by_name['agent.run']['id']
    assert by_name['home.light_on']['parent_run_id'] == by_name['agent.run']['id']
    assert by_name['agent.run']['parent_run_id'] == by_name['lifemate.sample']['id']
    assert by_name['lifemate.sample']['extra']['metadata']['sample_id'] == 'sample-test'
    assert len(requests) == 1
    messages = requests[0]['messages']
    assert [m['role'] for m in messages] == ['system', 'user', 'assistant', 'tool', 'user']
    assert messages[-1]['content'] == 'Bật đèn'
    assert messages[1]['content'] == 'Bật đèn'
    assert '<sample_context>' in messages[0]['content']
    assert '2026-11-16T11:30:00+07:00' in messages[0]['content']
    assert 'installed_apps' not in str(messages)
    assert 'available_tools' not in str(messages)
    call = messages[2]['tool_calls'][0]
    assert call['function']['name'] == requests[0]['tools'][0]['function']['name']
    assert messages[3]['tool_call_id'] == call['id']
    assert result['tool_calls'] == [{'name': 'home.light_on', 'arguments': {}}]
    assert set(result) == {'id', 'tool_calls', 'state_hash'}
    recorded = str(runs) + str(updates)
    assert 'DO_NOT_TRACE_LABEL' not in recorded
    assert 'test-key-never-exported' not in recorded
    llm_update = next(kw for args, kw in updates if str(kw.get("run_id", args[0] if args else None)) == str(by_name['vllm.chat']['id']))
    assert llm_update['outputs']['usage_metadata']['total_tokens'] == 15


def test_swallowed_provider_error_is_visible_in_trace(captured_traces, monkeypatch, tmp_path):
    class FailedAgent:
        def run_sync(self, *args, **kwargs):
            raise RuntimeError('provider unavailable')

    monkeypatch.setattr(runner, '_tool_env', lambda *args: Environment())
    monkeypatch.setattr(runner, 'build_agent', lambda *args: FailedAgent())
    runner.run_sample({'id': 'broken', 'audio_text': 'test'}, 'public_test', tmp_path, {}, object())
    runs, updates = captured_traces
    ids = {str(r['id']) for r in runs if r['name'] in {'agent.run', 'lifemate.sample'}}
    assert all(any(str(kw.get("run_id", args[0] if args else None)) == run_id and kw.get('error') == 'provider unavailable'
                   for args, kw in updates) for run_id in ids)


def test_disabled_tracing_does_not_construct_sdk_client(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING', 'false')
    monkeypatch.setattr(tracing, 'get_client', lambda: pytest.fail('SDK client should not be created'))
    client = object()
    assert tracing.wrap_llm_client(client) is client
    with tracing.trace_span('offline') as span:
        span.end(outputs={'ok': True})
    tracing.flush_traces()


def test_enabled_tracing_requires_key(monkeypatch):
    monkeypatch.setenv('LANGSMITH_TRACING', 'true')
    monkeypatch.setenv('LANGSMITH_API_KEY', '')
    with pytest.raises(ValueError, match='requires LANGSMITH_API_KEY'):
        tracing.initialize_tracing()


def test_dotenv_does_not_override_exported_settings(monkeypatch, tmp_path):
    dotenv = tmp_path / '.env'
    dotenv.write_text('LANGSMITH_TRACING=true\nLANGSMITH_API_KEY=from-file\n')
    monkeypatch.setattr(tracing, 'ENV_PATH', dotenv)
    monkeypatch.setenv('LANGSMITH_TRACING', 'false')
    monkeypatch.setenv('LANGSMITH_API_KEY', 'from-shell')
    tracing.initialize_tracing()
    assert not tracing.tracing_enabled()
    import os
    assert os.environ['LANGSMITH_API_KEY'] == 'from-shell'


def test_shared_model_reuses_live_loop_between_samples(captured_traces, monkeypatch, tmp_path):
    """A pooled HTTP transport keeps resources attached to its first event loop."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from lifemate.pydantic_agent import AgentDependencies, build_agent, run_agent

    loops = []

    async def respond(request):
        loop = asyncio.get_running_loop()
        if loops:
            assert not loops[0].is_closed(), 'Event loop is closed'
            assert loop is loops[0], 'Shared transport moved to another event loop'
        loops.append(loop)
        return httpx.Response(200, json={
            'id': 'chatcmpl-reuse', 'object': 'chat.completion', 'created': 1, 'model': 'qwen3-4b',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': 'Không cần thao tác.'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})

    client = AsyncOpenAI(base_url='http://localhost:8000/v1', api_key='local',
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    model = OpenAIChatModel('qwen3-4b', provider=OpenAIProvider(openai_client=tracing.wrap_llm_client(client)))

    def run_twice():
        try:
            for _ in range(2):
                deps = AgentDependencies(Environment(), {}, max_steps=8)
                result = run_agent(build_agent(model, deps), deps, 'Không cần làm gì.')
                assert getattr(deps, 'error', None) is None
                assert result is not None
            assert len(loops) == 2
        finally:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(client.close())
            loop.close()
            asyncio.set_event_loop(None)

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(run_twice).result()
