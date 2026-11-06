"""Compare two smoke-run JSON outputs against train references.

Usage: PYTHONPATH=src python -m experiments.math_framed_full_tools.compare \
    --root data/validation_300 --control control.json --treatment treatment.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from lifemate.agent_evaluation import tool_call_accuracy
from lifemate.data import load_catalog, read_jsonl, split_paths
from lifemate.agent_evaluation import TrainEvaluator


def _distribution(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        return {'count': 0, 'p50': None, 'p95': None, 'above_30s': 0}
    return {'count': len(ordered), 'p50': median(ordered),
            'p95': ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)],
            'above_30s': sum(value > 30 for value in ordered)}


def _calls(row: dict[str, Any]) -> list[dict[str, Any]]:
    return row.get('tool_calls', []) if isinstance(row.get('tool_calls'), list) else []


def _same_names(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    return Counter(call.get('name') for call in left) == Counter(call.get('name') for call in right)


def _completed(row: dict[str, Any] | None) -> bool:
    return (isinstance(row, dict) and not row.get('error')
            and isinstance(row.get('tool_calls'), list)
            and isinstance(row.get('state_hash'), str))


def compare_rows(control: list[dict[str, Any]], treatment: list[dict[str, Any]],
                 gold: dict[str, dict[str, Any]], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_arm = ({str(row['id']): row for row in arm} for arm in (control, treatment))
    control_by_id, treatment_by_id = by_arm
    universe = sorted(gold)
    result: dict[str, Any] = {'expected': len(universe)}
    for name, rows in (('control', control_by_id), ('treatment', treatment_by_id)):
        result[f'{name}_missing'] = [key for key in universe if key not in rows]
        result[f'{name}_errors'] = [key for key in universe if key in rows and not _completed(rows[key])]
        durations = [float(row['duration_seconds']) for row in rows.values()
                     if _completed(row) and isinstance(row.get('duration_seconds'), (int, float))]
        tokens = [float(row['total_tokens']) for row in rows.values()
                  if _completed(row) and isinstance(row.get('total_tokens'), (int, float))]
        result[f'{name}_latency'] = _distribution(durations)
        result[f'{name}_tokens'] = {'count': len(tokens), 'mean': sum(tokens) / len(tokens) if tokens else None}
    matched = [key for key in universe if _completed(control_by_id.get(key))
               and _completed(treatment_by_id.get(key))]
    result['matched'] = len(matched)
    result['tool_improved'] = []
    result['tool_regressed'] = []
    result['state_improved'] = []
    result['state_regressed'] = []
    result['argument_improved'] = []
    result['argument_regressed'] = []
    result['control_tool_correct'] = 0
    result['treatment_tool_correct'] = 0
    result['control_state_correct'] = 0
    result['treatment_state_correct'] = 0
    for key in matched:
        reference = gold[key]
        reference_calls = _calls(reference)
        old_calls, new_calls = _calls(control_by_id[key]), _calls(treatment_by_id[key])
        old_tool = bool(tool_call_accuracy(old_calls, reference_calls, catalog))
        new_tool = bool(tool_call_accuracy(new_calls, reference_calls, catalog))
        old_state = control_by_id[key]['state_hash'] == reference['state_hash']
        new_state = treatment_by_id[key]['state_hash'] == reference['state_hash']
        result['control_tool_correct'] += old_tool
        result['treatment_tool_correct'] += new_tool
        result['control_state_correct'] += old_state
        result['treatment_state_correct'] += new_state
        if old_tool != new_tool:
            result['tool_improved' if new_tool else 'tool_regressed'].append(key)
        if old_state != new_state:
            result['state_improved' if new_state else 'state_regressed'].append(key)
        old_arg_error = _same_names(old_calls, reference_calls) and not old_tool
        new_arg_error = _same_names(new_calls, reference_calls) and not new_tool
        if old_arg_error and new_tool:
            result['argument_improved'].append(key)
        if old_tool and new_arg_error:
            result['argument_regressed'].append(key)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--treatment', type=Path, required=True)
    parser.add_argument('--sample-ids-file', type=Path,
                        help='expected ID list; catches samples missing from both runs')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data_path, catalog_path = split_paths(args.root, 'train')
    evaluator = TrainEvaluator(args.root)
    samples = read_jsonl(data_path)
    gold = {str(sample['id']): evaluator.reference(sample) for sample in samples}
    catalog = load_catalog(catalog_path)
    control = json.loads(args.control.read_text(encoding='utf-8'))['rows']
    treatment = json.loads(args.treatment.read_text(encoding='utf-8'))['rows']
    ids = (set(args.sample_ids_file.read_text(encoding='utf-8').split())
           if args.sample_ids_file else {str(row['id']) for row in control + treatment})
    unknown = ids - gold.keys()
    if unknown:
        parser.error(f'unknown sample IDs: {sorted(unknown)}')
    result = compare_rows(control, treatment, {key: value for key, value in gold.items() if key in ids}, catalog)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')
    else:
        print(rendered)


if __name__ == '__main__':
    main()
