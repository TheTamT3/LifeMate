from lifemate.agent_policy import agent_instructions


def test_policy_does_not_add_case_ids_or_domain_specific_rules():
    text = agent_instructions()
    assert "train_" not in text
    assert "bill_payment" not in text
    assert "food_delivery" not in text


def test_build_agent_uses_composed_policy(monkeypatch):
    import sys
    import types
    from lifemate import pydantic_agent

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "pydantic_ai", types.SimpleNamespace(Agent=FakeAgent))
    monkeypatch.setattr(pydantic_agent, "_normalizing_model", lambda model, deps: model)
    monkeypatch.setattr(pydantic_agent, "build_tool_definitions", lambda deps: [])
    pydantic_agent.build_agent(object(), pydantic_agent.AgentDependencies(object(), {}, max_steps=10))
    assert captured["instructions"] == agent_instructions()
