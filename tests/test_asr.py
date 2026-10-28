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
