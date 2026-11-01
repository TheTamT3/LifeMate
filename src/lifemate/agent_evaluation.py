"""Local train checks; gold labels never enter the agent input."""
from __future__ import annotations

import importlib.util
import json
import re
import unicodedata
from pathlib import Path


def _tokens(value):
    text = unicodedata.normalize('NFD', str(value).lower()).replace('đ', 'd')
    return set(re.findall(r'[^\W_]+', ''.join(c for c in text if not unicodedata.combining(c))))


def _matches(actual, expected, schema):
    if schema.get('x-match') == 'fuzzy' and isinstance(actual, str) and isinstance(expected, str):
        left, right = _tokens(actual), _tokens(expected)
        return (2 * len(left & right) / (len(left) + len(right)) if left or right else 1) > .6
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _matches(actual[k], expected[k], schema.get('properties', {}).get(k, {})) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _matches(a, b, schema.get('items', {})) for a, b in zip(actual, expected))
    return actual == expected


def tool_call_accuracy(predicted, gold, catalog):
    """Binary full-call-set match using one-to-one maximum matching, not order."""
    if len(predicted) != len(gold):
        return 0
    matched = {}
    def assign(index, seen):
        call = predicted[index]
        for j, reference in enumerate(gold):
            if j in seen or call.get('name') != reference.get('name'):
                continue
            schema = catalog.get(call.get('name'), {}).get('parameters', {})
            if not _matches(call.get('arguments', {}), reference.get('arguments', {}), schema):
                continue
            seen.add(j)
            if j not in matched or assign(matched[j], seen):
                matched[j] = index
                return True
        return False
    return int(all(assign(i, set()) for i in range(len(predicted))))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrainEvaluator:
    def __init__(self, root):
        self.root = Path(root)
        runtime = self.root / 'train/zaic_tools'
        self.utils = _load(runtime / 'utils.py', 'lifemate_gold_utils')
        self.validate = _load(runtime / 'validate.py', 'lifemate_gold_validate')

    def reference(self, sample):
        label = sample.get('label')
        if not isinstance(label, dict) or not isinstance(label.get('tool_calls'), list) or not isinstance(label.get('final_state'), dict):
            raise ValueError(f"Sample {sample.get('id')} requires label.tool_calls and label.final_state")
        initial = json.loads((self.root / 'train/train_environment' / sample['id'] / 'state.json').read_text(encoding='utf-8'))
        initial.update(label['final_state'])
        return {'tool_calls': label['tool_calls'], 'state_hash': self.utils.state_hash(initial)}

    def publish(self, client, run_id, sample, result, reference, catalog):
        from .data import allowed_tools
        allowed = {tool['name'] for tool in allowed_tools(sample, catalog)}
        valid = all(self.validate.schema_error(call.get('name'), call.get('arguments'), catalog, allowed) is None
                    for call in result['tool_calls'])
        accuracy = int(valid and tool_call_accuracy(result['tool_calls'], reference['tool_calls'], catalog))
        state_match = int(result['state_hash'] == reference['state_hash'])
        for key, score, comment in (
            ('tool_call_accuracy', accuracy, 'Binary full call-set match; one-to-one matching, fuzzy token-F1 > 0.6; schema validation required.'),
            ('state_hash_match', state_match, f"expected={reference['state_hash']}; actual={result['state_hash']}"),
        ):
            client.create_feedback(run_id=run_id, key=key, score=score, comment=comment)
