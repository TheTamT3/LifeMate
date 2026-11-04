import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lifemate.experiments import dataset_rows, sync_dataset, score


def test_reference_labels_and_transcripts_never_enter_inputs(tmp_path, monkeypatch):
    split = tmp_path / 'train'
    split.mkdir()
    sample = {'id': 'train_1', 'audio': 'current.wav', 'audio_text': 'reference transcript',
              'context': {}, 'history': [{'role': 'user', 'audio': 'old.wav', 'audio_text': 'old reference'}],
              'label': {'tool_calls': [], 'final_state': {'secret': 'answer'}}}
    (split / 'train.jsonl').write_text(json.dumps(sample))
    class Env:
        def __init__(self, *args, **kwargs): pass
        def get_state_hash(self): return 'reference-hash'
    monkeypatch.setitem(sys.modules, 'zaic_tools', SimpleNamespace(ToolEnv=Env))
    digest, rows = dataset_rows(tmp_path)
    assert len(digest) == 64
    assert 'label' not in rows[0]['inputs']['sample']
    assert 'reference' not in json.dumps(rows[0]['inputs'])
    assert 'answer' not in json.dumps(rows[0]['inputs'])
    assert rows[0]['outputs']['state_hash'] == 'reference-hash'


def test_sync_is_idempotent_and_refuses_changed_reference():
    dataset = SimpleNamespace(id=uuid4(), metadata={'source_sha256': 'sha'})
    class Client:
        def __init__(self):
            self.examples = []
            self.writes = 0
        def read_dataset(self, **kwargs): return dataset
        def list_examples(self, **kwargs): return iter(self.examples)
        def create_examples(self, *, dataset_id, examples):
            self.writes += 1
            self.examples.extend(SimpleNamespace(**x) for x in examples)
    client = Client()
    rows = [{'inputs': {'sample': {'id': 's'}}, 'outputs': {'state_hash': 'a'}, 'metadata': {'sample_id': 's'}}]
    sync_dataset(client, 'validation', 'sha', rows)
    sync_dataset(client, 'validation', 'sha', rows)
    assert client.writes == 1
    rows[0] = {**rows[0], 'outputs': {'state_hash': 'changed'}}
    with pytest.raises(ValueError, match='differs'):
        sync_dataset(client, 'validation', 'sha', rows)
    with pytest.raises(ValueError, match='source changed'):
        sync_dataset(client, 'validation', 'other-sha', rows)


def test_scores_expose_latency_and_provider_failure_independently():
    run = SimpleNamespace(error=None, outputs={'tool_calls': [], 'state_hash': 'hash',
        'metrics': {'latency_seconds': 31, 'error': 'provider failed'}})
    reference = SimpleNamespace(outputs={'tool_calls': [], 'state_hash': 'hash'})
    scores = {r['key']: r['score'] for r in score(run, reference)['results']}
    assert scores == {'tool_calls_exact': True, 'state_hash_match': True,
                      'under_30s': False, 'pipeline_ok': False}
