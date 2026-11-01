import pytest

from lifemate.agent_evaluation import tool_call_accuracy


def test_calls_match_without_order_and_reject_duplicates():
    catalog = {'x': {'parameters': {'properties': {'id': {'type': 'integer'}}}}}
    gold = [{'name': 'x', 'arguments': {'id': i}} for i in (1, 2)]
    assert tool_call_accuracy(list(reversed(gold)), gold, catalog) == 1
    assert tool_call_accuracy([gold[0], gold[0]], gold, catalog) == 0
    assert tool_call_accuracy([], [], catalog) == 1
    assert tool_call_accuracy(gold, [], catalog) == 0


def test_fuzzy_strict_threshold_and_exact_other_arguments():
    catalog = {'x': {'parameters': {'properties': {'text': {'x-match': 'fuzzy'}}}}}
    gold = [{'name': 'x', 'arguments': {'text': 'a b c d e', 'id': 1}}]
    def predicted(text, ident=1):
        return [{'name': 'x', 'arguments': {'text': text, 'id': ident}}]
    assert tool_call_accuracy(predicted('a b c'), gold, catalog) == 1
    assert tool_call_accuracy(predicted('a b c x y'), gold, catalog) == 0
    assert tool_call_accuracy(predicted('a b c d e', 2), gold, catalog) == 0


def test_reference_uses_official_hash_and_partial_final_state(tmp_path):
    import json
    import shutil
    from pathlib import Path
    from lifemate.agent_evaluation import TrainEvaluator
    source = Path('train+public_test/train+public_test/train/zaic_tools')
    shutil.copytree(source, tmp_path / 'train' / 'zaic_tools', ignore=shutil.ignore_patterns('__pycache__'))
    state_path = tmp_path / 'train/train_environment/a/state.json'
    state_path.parent.mkdir(parents=True)
    state = {'tasks': {'items': []}, 'contacts': {'items': [{'id': 'c'}]}}
    state_path.write_text(json.dumps(state))
    evaluator = TrainEvaluator(tmp_path)
    sample = {'id': 'a', 'label': {'tool_calls': [], 'final_state': {'tasks': {'items': [1]}}}}
    reference = evaluator.reference(sample)
    expected = dict(state, tasks={'items': [1]})
    assert reference['state_hash'] == evaluator.utils.state_hash(expected)
    assert json.loads(state_path.read_text()) == state
    with pytest.raises(ValueError, match='label'):
        evaluator.reference({'id': 'a'})


@pytest.mark.parametrize('same_hash,expected', [(True, 1), (False, 0)])
def test_feedback_is_attached_to_each_sample_run(same_hash, expected):
    from types import SimpleNamespace
    from lifemate.agent_evaluation import TrainEvaluator
    evaluator = object.__new__(TrainEvaluator)
    evaluator.validate = SimpleNamespace(schema_error=lambda *args: None)
    feedback = []
    client = SimpleNamespace(create_feedback=lambda **kwargs: feedback.append(kwargs))
    evaluator.publish(client, 'sample-run', {'context': {}},
        {'tool_calls': [], 'state_hash': 'gold' if same_hash else 'wrong'},
        {'tool_calls': [], 'state_hash': 'gold'}, {})
    assert [(f['key'], f['score']) for f in feedback] == [
        ('tool_call_accuracy', 1), ('state_hash_match', expected)]
    assert all(f['run_id'] == 'sample-run' for f in feedback)


def test_schema_invalid_call_cannot_score_as_correct():
    from types import SimpleNamespace
    from lifemate.agent_evaluation import TrainEvaluator
    evaluator = object.__new__(TrainEvaluator)
    evaluator.validate = SimpleNamespace(schema_error=lambda *args: 'invalid schema')
    feedback = []
    calls = [{'name': 'bad', 'arguments': {}}]
    evaluator.publish(SimpleNamespace(create_feedback=lambda **kw: feedback.append(kw)), 'run', {},
        {'tool_calls': calls, 'state_hash': 'hash'}, {'tool_calls': calls, 'state_hash': 'hash'}, {})
    assert feedback[0]['score'] == 0
