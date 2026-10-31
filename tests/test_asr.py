from pathlib import Path
import sys
import types

import pytest

from lifemate.asr import ChunkFormerASR, transcript


class FakeASR:
    def __init__(self):
        self.paths = []

    def transcribe(self, audio_path: Path) -> str:
        self.paths.append(audio_path)
        return "Đà Nẵng có mưa không?"


def test_train_audio_text_is_used_without_asr():
    assert transcript({"audio_text": "Xin chào"}, None) == "Xin chào"


def test_audio_sample_uses_adapter_and_preserves_unicode():
    asr = FakeASR()
    assert transcript({"audio": "clip.wav"}, asr) == "Đà Nẵng có mưa không?"
    assert asr.paths == [Path("clip.wav")]


def test_missing_audio_adapter_fails_clearly():
    with pytest.raises(ValueError):
        transcript({"id": "x"}, None)


def test_chunkformer_adapter_uses_local_chunkformer_api(monkeypatch, tmp_path):
    class FakeModel:
        @classmethod
        def from_pretrained(cls, path):
            return cls()

        def endless_decode(self, **kwargs):
            return "xin chào"

    monkeypatch.setitem(sys.modules, "chunkformer", types.SimpleNamespace(ChunkFormerModel=FakeModel))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")
    adapter = ChunkFormerASR(tmp_path / "checkpoint")
    assert adapter.transcribe(audio) == "xin chào"
def test_chunkformer_adapter_forwards_decode_parameters(monkeypatch, tmp_path):
    calls = []

    class FakeModel:
        @classmethod
        def from_pretrained(cls, path):
            return cls()

        def endless_decode(self, **kwargs):
            calls.append(kwargs)
            return "xin chào"

    monkeypatch.setitem(sys.modules, "chunkformer", types.SimpleNamespace(ChunkFormerModel=FakeModel))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")
    adapter = ChunkFormerASR(
        tmp_path / "checkpoint",
        chunk_size=32,
        left_context_size=64,
        right_context_size=96,
    )

    adapter.transcribe(audio)

    assert calls == [
        {
            "audio_path": str(audio),
            "chunk_size": 32,
            "left_context_size": 64,
            "right_context_size": 96,
            "total_batch_duration": 14400,
        }
    ]


def test_qwen3_asr_adapter_uses_local_model_and_returns_text(monkeypatch, tmp_path):
    calls = []

    class FakeModel:
        def transcribe(self, **kwargs):
            calls.append(kwargs)
            return [types.SimpleNamespace(text="xin chào")]

    class FakeQwenModel:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls.append((path, kwargs))
            return FakeModel()

    monkeypatch.setitem(sys.modules, "qwen_asr", types.SimpleNamespace(Qwen3ASRModel=FakeQwenModel))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")

    from lifemate.asr import Qwen3ASR

    adapter = Qwen3ASR(tmp_path / "checkpoint", device="cpu")

    assert adapter.transcribe(audio) == "xin chào"
    assert calls[0][0] == str(tmp_path / "checkpoint")
    assert calls[1] == {"audio": str(audio), "language": "Vietnamese"}


def test_beam_adapter_checks_vocab_and_restores_model_after_failure(monkeypatch, tmp_path):
    import hashlib
    import json
    from lifemate.asr_eval.ctc_decoder import BackoffLM
    checkpoint=tmp_path/'checkpoint'; checkpoint.mkdir()
    vocab=checkpoint/'vocab.txt'; vocab.write_text('<blank> 0\n▁tắt 1\n')
    config={'version':1,'vocab_sha256':hashlib.sha256(vocab.read_bytes()).hexdigest(),
            'language_model':BackoffLM(['tắt']).to_dict(),'beam_width':4,'token_top_k':2,'alpha':.3,'beta':1.}
    artifact=tmp_path/'decoder.json'; artifact.write_text(json.dumps(config))
    class Model:
        char_dict={0:'<blank>',1:'▁tắt'}
        def endless_decode(self, **kwargs):
            assert self.char_dict is None
            raise RuntimeError('decode failed')
    model=Model(); adapter=ChunkFormerASR(checkpoint,ctc_decoder_path=artifact); adapter._pipeline=model
    audio=tmp_path/'a.wav'; audio.write_bytes(b'wav')
    with pytest.raises(RuntimeError,match='decode failed'): adapter.transcribe(audio)
    assert model.char_dict=={0:'<blank>',1:'▁tắt'}
    config['vocab_sha256']='wrong'; artifact.write_text(json.dumps(config))
    adapter=ChunkFormerASR(checkpoint,ctc_decoder_path=artifact)
    with pytest.raises(ValueError,match='vocabulary'): adapter.transcribe(audio)


def test_beam_adapter_decodes_acoustic_logits_with_loaded_artifact(tmp_path):
    import hashlib
    import json
    import numpy as np
    from lifemate.asr_eval.ctc_decoder import BackoffLM
    checkpoint=tmp_path/'checkpoint'; checkpoint.mkdir()
    vocab=checkpoint/'vocab.txt'; vocab.write_text('<blank> 0\n▁tắt 1\n▁đèn 2\n')
    artifact=tmp_path/'decoder.json'
    artifact.write_text(json.dumps({'version':1,'vocab_sha256':hashlib.sha256(vocab.read_bytes()).hexdigest(),
        'language_model':BackoffLM(['tắt đèn']).to_dict(),'beam_width':8,'token_top_k':3,'alpha':.3,'beta':1.}))
    class Logits:
        def float(self): return self
        def cpu(self): return self
        def numpy(self): return np.log([[.001,.998,.001],[.001,.001,.998]])
    class Model:
        char_dict={0:'<blank>',1:'▁tắt',2:'▁đèn'}
        def endless_decode(self, **kwargs):
            assert self.char_dict is None and kwargs['return_timestamps'] is False
            return Logits()
    model=Model(); adapter=ChunkFormerASR(checkpoint,ctc_decoder_path=artifact); adapter._pipeline=model
    audio=tmp_path/'a.wav'; audio.write_bytes(b'wav')
    assert adapter.transcribe(audio)=='tắt đèn'
    assert model.char_dict[1]=='▁tắt'
