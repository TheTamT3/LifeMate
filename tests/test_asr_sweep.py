from lifemate.asr_eval.sweep import DecodeConfig, default_grid


def test_default_grid_contains_baseline_and_unique_names():
    configs = default_grid()

    assert DecodeConfig(64, 128, 128) in configs
    assert len(configs) == len({config.name for config in configs})
    assert configs[0].name == "chunk64_left128_right128"
