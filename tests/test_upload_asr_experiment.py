from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

spec = spec_from_file_location('upload_asr_experiment', Path(__file__).parents[1] / 'scripts/upload_asr_experiment.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)


def evaluate(reference, prediction, error=None):
    run = SimpleNamespace(outputs={'transcript': prediction, 'error': error}, error=None)
    example = SimpleNamespace(outputs={'transcript': reference})
    return {r['key']: r['score'] for r in module.score(run, example)['results']}


def test_fuzzy_threshold_is_inclusive_and_normalizes_case_punctuation():
    result = evaluate('MỘT hai, ba.', 'một hai')
    assert result['fuzzy_token_f1'] == 0.8
    assert result['fuzzy_pass_0_8'] is True
    assert evaluate('một hai ba bốn', 'một hai')['fuzzy_pass_0_8'] is False


def test_failed_decode_cannot_pass_even_with_matching_text():
    result = evaluate('xin chào', 'xin chào', error='decoder failed')
    assert result['fuzzy_token_f1'] == 0
    assert result['fuzzy_pass_0_8'] is False
    assert result['pipeline_ok'] is False
