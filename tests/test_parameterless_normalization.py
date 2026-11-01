import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart
from pydantic_ai.models.function import FunctionModel

from lifemate.pydantic_agent import AgentDependencies, build_agent, run_agent


@pytest.mark.parametrize("kind", ["read", "write"])
@pytest.mark.parametrize("payload", ['{"arguments":"{}"}', '{"account_id":"c_05"}', {'location': 'home'}, '{}'])
def test_parameterless_calls_execute_without_retry_and_preserve_original(kind, payload):
    responses = []
    def model_fn(messages, info):
        response = ModelResponse(parts=[ToolCallPart('robot_vacuum_stop', payload, tool_call_id='call_1')]) if not responses else ModelResponse(parts=[TextPart('done')])
        responses.append(response)
        return response
    executed = []
    class Env:
        def call(self, name, args):
            executed.append((name, args))
            return {'ok': True}
    tool = {'name': 'robot_vacuum.stop', 'kind': kind, 'parameters': {'type': 'object', 'properties': {}}}
    deps = AgentDependencies(Env(), {tool['name']: tool}, 4)
    run_agent(build_agent(FunctionModel(model_fn), deps), deps, 'stop')
    assert getattr(deps, 'error', None) is None
    assert executed == [('robot_vacuum.stop', {})]
    assert len(responses) == (2 if kind == 'read' else 1)
    assert responses[0].parts[0].args == payload
    if payload != '{}':
        assert deps.argument_normalizations == [{
            'tool': 'robot_vacuum.stop', 'tool_call_id': 'call_1',
            'original_arguments': payload, 'normalized_arguments': {},
            'normalization_applied': True,
        }]
    else:
        assert deps.argument_normalizations == []


def test_optional_parameter_tool_keeps_validation_and_is_not_normalized():
    def model_fn(messages, info):
        return ModelResponse(parts=[ToolCallPart('phone_recent_calls', '{"arguments":"{}"}')])
    class Env:
        def call(self, name, args):
            pytest.fail('invalid arguments must not execute')
    tool = {'name': 'phone.recent_calls', 'kind': 'read', 'parameters': {
        'type': 'object', 'properties': {'missed_only': {'type': 'boolean'}}}}
    deps = AgentDependencies(Env(), {tool['name']: tool}, 4)
    run_agent(build_agent(FunctionModel(model_fn), deps), deps, 'calls')
    assert 'exceeded max retries' in deps.error
    assert deps.argument_normalizations == []


@pytest.mark.parametrize('name,payload', [
    ('robot_vacuum_stop', '{broken'),
    ('robot_vacuum_stop', '[]'),
    ('unknown_tool', '{"arguments":"{}"}'),
    ('phone_recent_calls', '{"missed_only":true}'),
])
def test_normalization_leaves_other_payloads_untouched(name, payload):
    from lifemate.pydantic_agent import _normalizing_model, run_agent_coroutine
    response = ModelResponse(parts=[ToolCallPart(name, payload)])
    def model_fn(messages, info):
        return response
    tools = {
        'robot_vacuum.stop': {'name': 'robot_vacuum.stop'},
        'phone.recent_calls': {'name': 'phone.recent_calls', 'parameters': {
            'type': 'object', 'properties': {'missed_only': {'type': 'boolean'}}}},
    }
    deps = AgentDependencies(None, tools, 4)
    from pydantic_ai.models import ModelRequestParameters
    result = run_agent_coroutine(_normalizing_model(FunctionModel(model_fn), deps).request(
        [], None, ModelRequestParameters()))
    assert result.parts[0].args == payload
    assert response.parts[0].args == payload
    assert deps.argument_normalizations == []
