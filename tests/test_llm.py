from lifemate.llm import LocalQwenAgent


def test_llm_does_not_quantize_by_default(tmp_path):
    agent = LocalQwenAgent(tmp_path / "model")
    assert agent.quantize is False


def test_llm_quantization_is_opt_in(tmp_path):
    agent = LocalQwenAgent(tmp_path / "model", quantize=True)
    assert agent.quantize is True
