import json
import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


@pytest.mark.parametrize('with_history', [False, True])
def test_agent_sends_one_leading_system_message_with_history(with_history):
    from lifemate.pydantic_agent import AgentDependencies, build_agent, run_agent
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

    payloads = []

    async def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'chatcmpl-system', 'object': 'chat.completion', 'created': 1,
            'model': 'qwen3-4b',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': 'Đã hiểu.'}}],
        })

    client = AsyncOpenAI(base_url='http://localhost:8000/v1', api_key='local',
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    model = OpenAIChatModel('qwen3-4b', provider=OpenAIProvider(openai_client=client))
    deps = AgentDependencies(None, {}, max_steps=8)
    history = [ModelRequest(parts=[UserPromptPart('Xin chào')]),
               ModelResponse(parts=[TextPart('Chào bạn')])]
    try:
        run_agent(build_agent(model, deps), deps, 'Yêu cầu hiện tại',
                  message_history=history if with_history else [], instructions='Ngữ cảnh riêng của mẫu')
        assert getattr(deps, 'error', None) is None
        messages = payloads[0]['messages']
        assert [i for i, message in enumerate(messages) if message['role'] == 'system'] == [0]
        assert 'Ngữ cảnh riêng của mẫu' in messages[0]['content']
        assert 'Bạn là trợ lý tiếng Việt' in messages[0]['content']
        assert [message['role'] for message in messages[1:]] == (
            ['user', 'assistant', 'user'] if with_history else ['user'])
    finally:
        from lifemate.pydantic_agent import run_agent_coroutine
        run_agent_coroutine(client.close())
