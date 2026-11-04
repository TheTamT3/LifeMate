"""Publish frozen ASR predictions as a LangSmith experiment without inference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

from lifemate.asr_eval.metrics import FUZZY_MATCH_THRESHOLD, transcript_metrics
from lifemate.tracing import initialize_tracing, get_client, flush_traces

NAMESPACE = UUID('84392b4b-f8c4-40c4-b2c7-50c82f01e682')


def score(run, example):
    output = run.outputs or {}
    metrics = transcript_metrics(example.outputs['transcript'], output.get('transcript', ''))
    ok = not output.get('error') and not run.error
    return {'results': [
        {'key': 'fuzzy_token_f1', 'score': metrics['fuzzy_token_f1'] if ok else 0.0,
         'comment': 'Multiset token F1; NFC, lowercase, punctuation removed; Vietnamese accents preserved.'},
        {'key': 'fuzzy_pass_0_8', 'score': bool(ok and metrics['fuzzy_match']),
         'comment': f"Pass iff no error and fuzzy_token_f1 >= {FUZZY_MATCH_THRESHOLD}."},
        {'key': 'wer_relaxed', 'score': metrics['relaxed_wer']},
        {'key': 'cer_relaxed', 'score': metrics['relaxed_cer']},
        {'key': 'pipeline_ok', 'score': bool(ok)},
    ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, default=Path('result/gipformer-1.5-benchmark'))
    parser.add_argument('--dataset', default='lifemate-asr-query-validation-300-v1')
    parser.add_argument('--experiment', default='gipformer15-query300-fuzzy08')
    parser.add_argument('--scope', choices=['query', 'all'], default='query')
    args = parser.parse_args()
    prediction_path = args.benchmark / 'predictions.jsonl'
    rows = [json.loads(line) for line in prediction_path.read_text().splitlines() if line.strip()]
    if args.scope == 'query':
        rows = [row for row in rows if row['turn'] == 'query']
    if not rows:
        raise ValueError('No predictions for selected scope')
    identity = lambda row: f"{row['sample_id']}:{row['turn']}"
    cached = {identity(row): row for row in rows}
    if len(cached) != len(rows):
        raise ValueError('Duplicate sample/turn identities')
    references = [{'key': identity(row), 'reference': row['reference']} for row in rows]
    digest = hashlib.sha256(json.dumps(references, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    initialize_tracing()
    client = get_client()
    from langsmith.utils import LangSmithNotFoundError
    try:
        dataset = client.read_dataset(dataset_name=args.dataset)
    except LangSmithNotFoundError:
        dataset = client.create_dataset(dataset_name=args.dataset,
            description='Frozen ASR validation: one row per selected utterance; references separate from audio input.',
            metadata={'reference_sha256': digest, 'samples': len({r['sample_id'] for r in rows}), 'utterances': len(rows)})
    if (dataset.metadata or {}).get('reference_sha256') != digest:
        raise ValueError('Dataset references changed; use a different dataset name')
    existing = {str(e.id): e for e in client.list_examples(dataset_id=dataset.id)}
    pending = []
    for row in rows:
        key = identity(row)
        entry = {'id': str(uuid5(NAMESPACE, f'{dataset.id}:{key}')),
                 'inputs': {'sample_id': row['sample_id'], 'turn': row['turn'],
                            'audio': str(Path(row['audio']).relative_to(Path.cwd()))},
                 'outputs': {'transcript': row['reference']}, 'metadata': {'utterance_key': key}}
        old = existing.get(entry['id'])
        if old and (old.inputs != entry['inputs'] or old.outputs != entry['outputs']):
            raise ValueError(f'Existing example differs: {key}')
        if not old:
            pending.append(entry)
    for start in range(0, len(pending), 100):
        client.create_examples(dataset_id=dataset.id, examples=pending[start:start+100])
    examples = list(client.list_examples(dataset_id=dataset.id))
    if len(examples) != len(rows):
        raise ValueError('Unexpected dataset size')

    def target(inputs):
        from langsmith import get_current_run_tree

        row = cached[identity(inputs)]
        tree = get_current_run_tree()
        if tree is not None:
            tree.add_metadata({'original_asr_latency_seconds': row.get('latency_seconds'),
                               'source': 'cached_benchmark_no_inference'})
        output = {'transcript': row.get('prediction', '')}
        if row.get('error'):
            output['error'] = row['error']
        return output

    metadata = json.loads((args.benchmark / 'metadata.json').read_text())
    metadata.update({'scope': args.scope, 'sample_count': len({r['sample_id'] for r in rows}),
                     'utterance_count': len(rows), 'evaluation_mode': 'cached_predictions_no_inference',
                     'predictions_sha256': hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
                     'fuzzy_metric': 'relaxed_multiset_token_f1', 'fuzzy_threshold': FUZZY_MATCH_THRESHOLD,
                     'latency_note': 'Run latency is cache lookup/upload; original ASR latency is in run metadata.'})
    try:
        results = client.evaluate(target, data=examples, evaluators=[score],
            experiment_prefix=args.experiment, metadata=metadata, max_concurrency=1)
        evaluated = list(results)
        passed = sum(not r.get('error') and transcript_metrics(r['reference'], r.get('prediction', ''))['fuzzy_match'] for r in rows)
        report = {'experiment': results.experiment_name, 'experiment_id': str(results.experiment_id),
                  'dataset_id': str(dataset.id), 'url': results.url, 'utterances': len(evaluated),
                  'fuzzy_pass': passed, 'fuzzy_fail': len(rows)-passed,
                  'rows': [{'run_id': str(r['run'].id), 'example_id': str(r['example'].id)} for r in evaluated]}
        (args.benchmark / f'langsmith-experiment-{args.scope}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k:v for k,v in report.items() if k != 'rows'}), flush=True)
    finally:
        flush_traces()


if __name__ == '__main__':
    main()
