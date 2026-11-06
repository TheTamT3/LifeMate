import copy
import json

import pytest

from lifemate.oracle import prepare_oracle_inputs


def fixture_data(tmp_path):
    catalog = {
        'calendar.update': {'name': 'calendar.update', 'app': 'calendar', 'parameters': {
            'type': 'object', 'properties': {'contact_id': {'type': 'string', 'x-ref': 'contacts.contacts'}}}},
        'calendar.list': {'name': 'calendar.list', 'app': 'calendar'},
        'sys.ask_missing_info': {'name': 'sys.ask_missing_info', 'app': 'sys', 'kind': 'meta'},
    }
    sample = {'id': 'train_1', 'audio_text': 'request', 'context': {'installed_apps': {
        'calendar': {'tools': ['calendar.update', 'calendar.list']}}},
        'label': {'tool_calls': [
            {'name': 'calendar.update', 'arguments': {'secret': 'GOLD_ARGUMENT'}},
            {'name': 'calendar.list', 'arguments': {}},
            {'name': 'calendar.update', 'arguments': {}}],
            'tool_results': [{'secret': 'GOLD_RESULT'}], 'final_state': {'secret': 'GOLD_FINAL'}}}
    state = {'_meta': {'secret': 'META'}, 'calendar': {'events': [{'id': 'initial'}]},
             'contacts': {'contacts': [{'id': 'c1'}]}, 'banking': {'secret': 'UNRELATED'}}
    path = tmp_path / 'train/train_environment/train_1'
    path.mkdir(parents=True)
    (path / 'state.json').write_text(json.dumps(state), encoding='utf-8')
    return sample, catalog


def test_prepares_only_unique_sorted_names_without_state(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    original = copy.deepcopy(sample)
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    assert prepared.tool_names == ('calendar.list', 'calendar.update')
    assert not hasattr(prepared, 'source_context')
    assert 'GOLD' not in repr(prepared)
    assert sample == original


def test_empty_calls_do_not_add_system_tool_or_require_state(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    sample['label']['tool_calls'] = []
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path / 'absent', 'train')
    assert prepared.tool_names == ()
    assert not hasattr(prepared, 'source_context')


@pytest.mark.parametrize('split', ['public_test', 'private_test'])
def test_requires_train(tmp_path, split):
    sample, catalog = fixture_data(tmp_path)
    with pytest.raises(ValueError, match='train'):
        prepare_oracle_inputs(sample, catalog, tmp_path, split)


@pytest.mark.parametrize('label', [None, {}, {'tool_calls': None}, {'tool_calls': [{}]},
                                   {'tool_calls': [{'name': 'unknown'}]}])
def test_invalid_labels_fail_closed(tmp_path, label):
    sample, catalog = fixture_data(tmp_path)
    sample['label'] = label
    with pytest.raises(ValueError):
        prepare_oracle_inputs(sample, catalog, tmp_path, 'train')


def test_unavailable_tool_rejected(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    sample['context']['installed_apps'] = {}
    with pytest.raises(ValueError, match='available'):
        prepare_oracle_inputs(sample, catalog, tmp_path, 'train')


def test_system_only_needs_no_app_source(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    sample['label']['tool_calls'] = [{'name': 'sys.ask_missing_info'}]
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path / 'absent', 'train')
    assert prepared.tool_names == ('sys.ask_missing_info',)
    assert not hasattr(prepared, 'source_context')


def test_runner_excludes_state_and_preserves_autonomous_zero_calls(tmp_path, monkeypatch):
    from lifemate import runner
    sample, catalog = fixture_data(tmp_path)
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    captured = {}

    class Env:
        def get_tool_calls(self): return []
        def get_state_hash(self): return 'unchanged'

    monkeypatch.setattr(runner, '_tool_env', lambda *a: Env())
    monkeypatch.setattr(runner, 'build_agent', lambda model, deps, **kw: captured.update(tools=deps.tools_by_name, agent_options=kw))
    monkeypatch.setattr(runner, 'run_agent', lambda agent, deps, prompt, **kw: captured.update(prompt=prompt, **kw))
    result = runner.run_sample(sample, 'train', tmp_path, catalog, None, oracle_inputs=prepared)
    assert set(captured['tools']) == set(prepared.tool_names)
    assert captured['prompt'] == 'request'
    assert 'initial' not in captured['instructions'] and 'source_context' not in captured['instructions']
    assert 'GOLD' not in str(captured)
    assert result['tool_calls'] == []
    assert result['oracle']['tool_names'] == list(prepared.tool_names)
    from lifemate.oracle import ORACLE_INSTRUCTIONS
    assert captured['agent_options'] == {'instructions': ORACLE_INSTRUCTIONS}
    assert set(json.loads(captured['instructions'])) == {'context'}

    captured.clear()
    sample['source_context'] = {'secret': 'UNTRUSTED_SOURCE'}
    baseline = runner.run_sample(sample, 'train', tmp_path, catalog, None)
    assert captured['prompt'] == 'request'
    assert 'sys.ask_missing_info' in captured['tools']
    assert 'oracle' not in baseline
    assert captured['agent_options'] == {}


def test_full_tools_mode_preserves_oracle_prompt_and_context(tmp_path, monkeypatch):
    from lifemate import runner
    from lifemate.oracle import ORACLE_INSTRUCTIONS

    sample, catalog = fixture_data(tmp_path)
    sample['context']['current_time'] = '2026-11-05T09:00:00+07:00'
    sample['history'] = [{'role': 'user', 'content': 'Earlier request'}]
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    captured = []

    class Env:
        def get_tool_calls(self): return []
        def get_state_hash(self): return 'unchanged'

    monkeypatch.setattr(runner, '_tool_env', lambda *a: Env())
    monkeypatch.setattr(runner, '_to_model_messages', lambda records: records)

    def capture_agent(model, deps, **kwargs):
        captured.append({'tools': tuple(deps.tools_by_name), 'options': kwargs})
        return None

    def capture_run(agent, deps, prompt, **kwargs):
        captured[-1].update({'prompt': prompt, 'run': kwargs})

    monkeypatch.setattr(runner, 'build_agent', capture_agent)
    monkeypatch.setattr(runner, 'run_agent', capture_run)
    runner.run_sample(sample, 'train', tmp_path, catalog, None, oracle_inputs=prepared)
    full_sample = copy.deepcopy(sample)
    full_sample.pop('label')
    result = runner.run_sample(full_sample, 'train', tmp_path, catalog, None,
                               oracle_context_full_tools=True)

    oracle_call, full_call = captured
    assert set(oracle_call['tools']) == {'calendar.list', 'calendar.update'}
    assert set(full_call['tools']) == {
        'calendar.list', 'calendar.update', 'sys.ask_missing_info'}
    assert oracle_call['options'] == full_call['options'] == {'instructions': ORACLE_INSTRUCTIONS}
    assert oracle_call['prompt'] == full_call['prompt'] == 'request'
    assert oracle_call['run'] == full_call['run']
    assert set(json.loads(full_call['run']['instructions'])) == {'context'}
    assert 'installed_apps' not in full_call['run']['instructions']
    assert 'oracle' not in result


def test_math_framed_mode_changes_only_agent_instructions(tmp_path, monkeypatch):
    from lifemate import runner
    from lifemate.math_prompt import MATH_FRAMED_INSTRUCTIONS, MATH_PROMPT_VERSION

    sample, catalog = fixture_data(tmp_path)
    sample.pop('label')
    sample['history'] = [{'role': 'user', 'content': 'Earlier request'}]
    captured = []

    class Env:
        def get_tool_calls(self): return []
        def get_state_hash(self): return 'unchanged'

    monkeypatch.setattr(runner, '_tool_env', lambda *a: Env())
    monkeypatch.setattr(runner, '_to_model_messages', lambda records: records)

    def capture_agent(model, deps, **kwargs):
        captured.append({'tools': copy.deepcopy(deps.tools_by_name), 'agent_options': kwargs,
                         'max_steps': deps.max_steps, 'seed': deps.seed})
        return None

    def capture_run(agent, deps, prompt, **kwargs):
        captured[-1].update({'prompt': prompt, 'run': kwargs})

    monkeypatch.setattr(runner, 'build_agent', capture_agent)
    monkeypatch.setattr(runner, 'run_agent', capture_run)
    runner.run_sample(sample, 'train', tmp_path, catalog, None,
                      oracle_context_full_tools=True, max_steps=10, seed=0)
    result = runner.run_sample(sample, 'train', tmp_path, catalog, None,
                               math_framed_full_tools=True, max_steps=10, seed=0)
    control, treatment = captured
    assert control['tools'] == treatment['tools']
    assert control['max_steps'] == treatment['max_steps'] == 10
    assert control['seed'] == treatment['seed'] == 0
    assert control['prompt'] == treatment['prompt']
    assert control['run'] == treatment['run']
    assert control['agent_options'] != treatment['agent_options']
    assert treatment['agent_options'] == {'instructions': MATH_FRAMED_INSTRUCTIONS}
    assert result['math_framed_full_tools']['prompt_version'] == MATH_PROMPT_VERSION


def test_math_framed_mode_rejects_oracle_and_non_train(tmp_path):
    from lifemate import runner
    sample, catalog = fixture_data(tmp_path)
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    with pytest.raises(ValueError, match='mutually exclusive'):
        runner.run_sample(sample, 'train', tmp_path, catalog, None,
                          oracle_inputs=prepared, math_framed_full_tools=True)
    with pytest.raises(ValueError, match='train'):
        runner.run_sample(sample, 'public_test', tmp_path, catalog, None,
                          math_framed_full_tools=True)


def test_preparation_needs_no_state_file(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    assert prepare_oracle_inputs(sample, catalog, tmp_path / 'absent', 'train').tool_names == ('calendar.list', 'calendar.update')


def test_gold_order_arguments_and_results_do_not_change_inputs(tmp_path):
    sample, catalog = fixture_data(tmp_path)
    before = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    sample['label'] = {'tool_calls': [{'name': 'calendar.list'}, {'name': 'calendar.update'}]}
    assert prepare_oracle_inputs(sample, catalog, tmp_path, 'train') == before


@pytest.mark.parametrize('selected,choose_call', [(['calendar.list'], False),
                                                (['calendar.list'], True), ([], False)])
def test_real_sdk_request_has_only_selected_tools_and_auto_choice(tmp_path, monkeypatch, selected, choose_call):
    import httpx
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from lifemate import runner
    from lifemate.pydantic_agent import agent_event_loop

    sample, catalog = fixture_data(tmp_path)
    sample['context']['current_time'] = '2026-11-05T09:00:00+07:00'
    # These fields are deliberately outside the allowed model inputs.
    for field in ('source_context', 'state', 'final_state', 'tool_calls', 'state_hash'):
        sample[field] = {'secret': 'FORBIDDEN_TOP_LEVEL_DATA'}
    sample['history'] = [{'role': 'assistant', 'tool_calls': [
        {'name': 'calendar.update', 'arguments': {'contact_id': 'c1'}}],
        'tool_results': [{'ok': True}]}]
    sample['label']['tool_calls'] = [{'name': name} for name in selected]
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if choose_call and len(requests) == 1:
            return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion',
                'created': 1, 'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'model-choice', 'type': 'function', 'function': {
                        'name': 'calendar_list', 'arguments': '{}'}}]}}]})
        # The model may choose to finish without calling any available tool.
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion',
            'created': 1, 'model': 'test', 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': 'done'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}})

    class Env:
        def __init__(self): self.calls = []
        def call(self, name, arguments):
            self.calls.append({'name': name, 'arguments': arguments})
            return {'ok': True, 'events': [{'id': 'initial'}]}
        def get_tool_calls(self): return self.calls
        def get_state_hash(self): return 'unchanged'

    monkeypatch.setattr(runner, '_tool_env', lambda *a: Env())
    client = AsyncOpenAI(api_key='local', base_url='http://test/v1',
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    model = OpenAIChatModel('test', provider=OpenAIProvider(openai_client=client))
    with agent_event_loop() as loop:
        try:
            result = runner.run_sample(sample, 'train', tmp_path, catalog, model, oracle_inputs=prepared)
        finally:
            loop.run(client.close())
    assert result['tool_calls'] == ([{'name': 'calendar.list', 'arguments': {}}] if choose_call else [])
    assert len(requests) == (2 if choose_call else 1)
    body = requests[0]
    assert [t['function']['name'] for t in body.get('tools', [])] == ['calendar_list' for _ in selected]
    assert body.get('tool_choice', 'auto') == 'auto'
    assert 'source_context' not in str(body['messages'])
    assert 'initial' not in str(body['messages'])
    assert 'GOLD' not in str(body)
    assert 'FORBIDDEN_TOP_LEVEL_DATA' not in str(requests)
    from lifemate.oracle import ORACLE_INSTRUCTIONS
    system_messages = [m for m in body['messages'] if m['role'] == 'system']
    assert len(system_messages) == 1
    system_text = system_messages[0]['content']
    assert system_text.startswith(ORACLE_INSTRUCTIONS)
    payload = json.loads(system_text[len(ORACLE_INSTRUCTIONS):].strip())
    user = next(m for m in body['messages'] if m['role'] == 'user')
    assert user['content'] == 'request'
    assert 'context' in payload
    assert payload['context']['current_time'] == sample['context']['current_time']
    assert 'installed_apps' not in payload['context']
    assert set(payload) == {'context'}
    for request in requests:
        assert next(m['content'] for m in request['messages'] if m['role'] == 'system') == system_text
    history_call = next(m for m in body['messages'] if m.get('tool_calls'))
    assert history_call['tool_calls'][0]['function']['name'] == 'calendar_update'


def smoke_module():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'scripts/smoke_e2e_langsmith.py'
    spec = importlib.util.spec_from_file_location('oracle_smoke_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_rejects_non_train_before_loading_credentials(monkeypatch):
    module = smoke_module()
    monkeypatch.setattr(module, 'load_dotenv', lambda *a, **kw: pytest.fail('credentials loaded'))
    with pytest.raises(SystemExit) as error:
        module.main(['--root', 'unused', '--split', 'public_test', '--limit', '1',
                     '--model', 'unused', '--oracle-tools-source'])
    assert error.value.code == 2


@pytest.mark.parametrize('extra', [
    ['--oracle-tools-source', '--oracle-context-full-tools'],
    ['--oracle-context-full-tools', '--split', 'public_test'],
    ['--oracle-context-full-tools', '--concurrency', '0'],
    ['--oracle-context-full-tools', '--concurrency', '32'],
    ['--math-framed-full-tools', '--oracle-context-full-tools'],
    ['--math-framed-full-tools', '--oracle-tools-source'],
    ['--math-framed-full-tools', '--split', 'public_test'],
])
def test_cli_rejects_invalid_experiment_or_concurrency_before_credentials(monkeypatch, extra):
    module = smoke_module()
    monkeypatch.setattr(module, 'load_dotenv', lambda *a, **kw: pytest.fail('credentials loaded'))
    with pytest.raises(SystemExit) as error:
        module.main(['--root', 'unused', '--sample-id', 'train_1', '--model', 'unused', *extra])
    assert error.value.code == 2


def test_traced_runner_forwards_prepared_input_and_strips_label(tmp_path):
    from types import SimpleNamespace
    module = smoke_module()
    sample, catalog = fixture_data(tmp_path)
    prepared = prepare_oracle_inputs(sample, catalog, tmp_path, 'train')
    captured = {}

    def run_sample(sample_for_run, **kwargs):
        captured.update(sample=sample_for_run, **kwargs)
        return {'id': sample_for_run['id'], 'tool_calls': [], 'state_hash': 'initial'}

    runner = SimpleNamespace(_tool_env=lambda *a: None, transcript=lambda *a: 'request',
                             run_agent=lambda *a: None, run_sample=run_sample)
    client = SimpleNamespace(create_run=lambda **kw: None, update_run=lambda *a, **kw: None)
    args = SimpleNamespace(use_reference_text=True, asr_backend='gipformer', split='train',
        llm_model_name='test', example_ids={'train_1': None}, root=tmp_path,
        max_steps=10, seed=0, oracle_inputs={'train_1': prepared})
    result = module._run_one_sample(sample, args=args, catalog=catalog, runner=runner,
                                    llm=None, asr=None, client=client, project='test')
    assert 'error' not in result
    assert captured['oracle_inputs'] is prepared
    assert 'label' not in captured['sample']


def test_traced_runner_forwards_full_tools_mode_without_label(tmp_path):
    from types import SimpleNamespace
    module = smoke_module()
    sample, catalog = fixture_data(tmp_path)
    captured = {}

    def run_sample(sample_for_run, **kwargs):
        captured.update(sample=sample_for_run, **kwargs)
        return {'id': sample_for_run['id'], 'tool_calls': [], 'state_hash': 'initial'}

    runner = SimpleNamespace(_tool_env=lambda *a: None, transcript=lambda *a: 'request',
                             run_agent=lambda *a: None, run_sample=run_sample)
    client = SimpleNamespace(create_run=lambda **kw: None, update_run=lambda *a, **kw: None)
    args = SimpleNamespace(use_reference_text=True, asr_backend='gipformer', split='train',
        llm_model_name='test', example_ids={'train_1': None}, root=tmp_path,
        max_steps=10, seed=0, oracle_inputs={}, oracle_context_full_tools=True)
    result = module._run_one_sample(sample, args=args, catalog=catalog, runner=runner,
                                    llm=None, asr=None, client=client, project='test')
    assert 'error' not in result
    assert captured['oracle_context_full_tools'] is True
    assert 'oracle_inputs' not in captured
    assert 'label' not in captured['sample']


def test_traced_runner_forwards_math_mode_without_label(tmp_path):
    from types import SimpleNamespace
    module = smoke_module()
    sample, catalog = fixture_data(tmp_path)
    captured = {}

    def run_sample(sample_for_run, **kwargs):
        captured.update(sample=sample_for_run, **kwargs)
        return {'id': sample_for_run['id'], 'tool_calls': [], 'state_hash': 'initial'}

    runner = SimpleNamespace(_tool_env=lambda *a: None, transcript=lambda *a: 'request',
                             run_agent=lambda *a: None, run_sample=run_sample)
    client = SimpleNamespace(create_run=lambda **kw: None, update_run=lambda *a, **kw: None)
    args = SimpleNamespace(use_reference_text=True, asr_backend='gipformer', split='train',
        llm_model_name='test', example_ids={'train_1': None}, root=tmp_path,
        max_steps=10, seed=0, oracle_inputs={}, math_framed_full_tools=True)
    result = module._run_one_sample(sample, args=args, catalog=catalog, runner=runner,
                                    llm=None, asr=None, client=client, project='test')
    assert 'error' not in result
    assert captured['math_framed_full_tools'] is True
    assert 'oracle_inputs' not in captured
    assert 'label' not in captured['sample']


def test_parallel_dispatch_uses_32_workers_and_keeps_sample_order(monkeypatch):
    from types import SimpleNamespace
    module = smoke_module()
    samples = [{'id': f'train_{i}'} for i in range(3)]
    observed = {}

    class Pool:
        def __init__(self, max_workers, mp_context):
            observed['max_workers'] = max_workers
            observed['mp_context'] = mp_context
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def map(self, fn, tasks):
            observed['tasks'] = list(tasks)
            return ({'id': task[0]['id']} for task in reversed(observed['tasks']))

    monkeypatch.setattr(module, 'ProcessPoolExecutor', Pool, raising=False)
    args = SimpleNamespace(concurrency=32, use_reference_text=True, split='train',
        root='unused', oracle_inputs={}, example_ids={sample['id']: None for sample in samples},
        references={sample['id']: {} for sample in samples})
    rows = module._execute_samples(samples, args=args, catalog={}, runner=None,
                                   llm=None, asr=None, client=None, project='test')
    assert observed['max_workers'] == 32
    assert len(observed['tasks']) == 3
    assert {task[0]['id'] for task in observed['tasks']} == {sample['id'] for sample in samples}
    assert [row['id'] for row in rows] == [sample['id'] for sample in samples]


def test_saved_300_ids_are_unique():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'experiments/oracle_tools_source/sample_ids_300.txt'
    ids = path.read_text(encoding='utf-8').split()
    assert len(ids) == len(set(ids)) == 300


def test_preparation_never_reads_state(tmp_path, monkeypatch):
    from pathlib import Path
    sample, catalog = fixture_data(tmp_path)
    monkeypatch.setattr(Path, 'read_text', lambda *a, **kw: pytest.fail('state read forbidden'))
    assert prepare_oracle_inputs(sample, catalog, tmp_path, 'train').tool_names == ('calendar.list', 'calendar.update')
