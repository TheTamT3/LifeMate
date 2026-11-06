from experiments.math_framed_full_tools.compare import compare_rows


def test_pilot_has_fixed_disjoint_strata_from_300():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    pilot = (root / 'experiments/math_framed_full_tools/pilot_sample_ids.txt').read_text().split()
    full = (root / 'experiments/oracle_tools_source/sample_ids_300.txt').read_text().split()
    prior_arg = (root / 'review_data/version_5efb0ae0_review_20261104/sample_ids_arg.txt').read_text().split()
    assert len(pilot) == len(set(pilot)) == 20
    assert set(pilot) <= set(full)
    assert set(pilot[:10]) <= set(prior_arg)
    assert not set(pilot[10:]) & set(prior_arg)


def test_comparison_pairs_completed_rows_and_reports_regression_and_missing():
    gold = {
        'a': {'tool_calls': [{'name': 't', 'arguments': {'x': 1}}], 'state_hash': 'A'},
        'b': {'tool_calls': [{'name': 't', 'arguments': {'x': 2}}], 'state_hash': 'B'},
        'c': {'tool_calls': [], 'state_hash': 'C'},
    }
    control = [
        {'id': 'a', 'tool_calls': [{'name': 't', 'arguments': {'x': 0}}], 'state_hash': 'bad', 'duration_seconds': 31},
        {'id': 'b', 'tool_calls': [{'name': 't', 'arguments': {'x': 2}}], 'state_hash': 'B', 'duration_seconds': 8},
        {'id': 'c', 'error': 'timeout'},
    ]
    treatment = [
        {'id': 'a', 'tool_calls': [{'name': 't', 'arguments': {'x': 1}}], 'state_hash': 'A', 'duration_seconds': 9},
        {'id': 'b', 'tool_calls': [{'name': 't', 'arguments': {'x': 0}}], 'state_hash': 'bad', 'duration_seconds': 32},
    ]
    result = compare_rows(control, treatment, gold, {'t': {'parameters': {'type': 'object'}}})
    assert result['matched'] == 2
    assert result['control_errors'] == ['c']
    assert result['treatment_missing'] == ['c']
    assert result['tool_improved'] == ['a']
    assert result['tool_regressed'] == ['b']
    assert result['argument_improved'] == ['a']
    assert result['argument_regressed'] == ['b']
    assert result['control_latency']['above_30s'] == 1
    assert result['treatment_latency']['above_30s'] == 1


def test_comparison_handles_absent_optional_usage_and_latency():
    gold = {'a': {'tool_calls': [], 'state_hash': 'A'}}
    rows = [{'id': 'a', 'tool_calls': [], 'state_hash': 'A'}]
    result = compare_rows(rows, rows, gold, {})
    assert result['matched'] == 1
    assert result['control_latency']['count'] == 0
    assert result['control_tokens']['count'] == 0
