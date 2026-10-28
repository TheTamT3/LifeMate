import sys
import types
from pathlib import Path

from lifemate.asr import ChunkFormerASR


def test_chunkformer_adapter_batch_fallback_preserves_order(monkeypatch, tmp_path):
    class FakeModel:
        @classmethod
        def from_pretrained(cls, path):
            return cls()

        def endless_decode(self, **kwargs):
            return {"text": Path(kwargs["audio_path"]).stem}

    monkeypatch.setitem(sys.modules, "chunkformer", types.SimpleNamespace(ChunkFormerModel=FakeModel))
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"wav")
    second.write_bytes(b"wav")
    adapter = ChunkFormerASR(tmp_path / "checkpoint")

    assert adapter.transcribe_batch([first, second]) == ["first", "second"]


def test_chunkformer_adapter_applies_explicit_device(monkeypatch, tmp_path):
    class FakeModel:
        moved_to = None

        @classmethod
        def from_pretrained(cls, path):
            return cls()

        def to(self, device):
            self.moved_to = device
            return self

        def endless_decode(self, **kwargs):
            return {"text": "ok"}

    monkeypatch.setitem(sys.modules, "chunkformer", types.SimpleNamespace(ChunkFormerModel=FakeModel))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")
    adapter = ChunkFormerASR(tmp_path / "checkpoint", device="cpu")

    adapter.transcribe(audio)

    assert adapter._pipeline.moved_to == "cpu"
