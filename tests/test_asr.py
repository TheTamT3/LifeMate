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
