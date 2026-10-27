import random

import pytest

from lifemate.config import RuntimeConfig, seed_everything


def test_runtime_config_defaults_and_context_limit(tmp_path):
    config = RuntimeConfig(tmp_path / "qwen", tmp_path / "asr")
    assert config.max_steps == 8
    assert config.max_new_tokens == 512
    with pytest.raises(ValueError):
        RuntimeConfig(tmp_path / "qwen", tmp_path / "asr", context_length=16_385)


def test_seed_everything_makes_python_random_repeatable():
    seed_everything(7)
    first = [random.random() for _ in range(3)]
    seed_everything(7)
    assert first == [random.random() for _ in range(3)]
