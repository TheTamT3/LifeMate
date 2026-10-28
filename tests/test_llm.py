from lifemate.llm import LocalQwenAgent


def test_llm_generation_keeps_kv_cache_enabled(monkeypatch, tmp_path):
    import sys

    class FakeTensor:
        shape = (1, 3)

        def __getitem__(self, _key):
            return self

    class FakeTorch:
        @staticmethod
        def inference_mode():
            class Context:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

            return Context()

    monkeypatch.setitem(sys.modules, "torch", FakeTorch())

    class FakeInputs(dict):
        def to(self, _device):
            return self

    class FakeTokenizer:
        def apply_chat_template(self, *_args, **_kwargs):
            return "prompt"

        def __call__(self, *_args, **_kwargs):
            return FakeInputs(input_ids=FakeTensor(), attention_mask=FakeTensor())

        def decode(self, *_args, **_kwargs):
            return "{}"

    class FakeModel:
        device = "cpu"

        def generate(self, **kwargs):
            assert kwargs["use_cache"] is True
            return FakeTensor()

    agent = LocalQwenAgent(tmp_path / "model")
    agent._tokenizer = FakeTokenizer()
    agent._model = FakeModel()
    agent.generate("hello")


def test_llm_does_not_quantize_by_default(tmp_path):
    agent = LocalQwenAgent(tmp_path / "model")
    assert agent.quantize is False


def test_llm_quantization_is_opt_in(tmp_path):
    agent = LocalQwenAgent(tmp_path / "model", quantize=True)
    assert agent.quantize is True
