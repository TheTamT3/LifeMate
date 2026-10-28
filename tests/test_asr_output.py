import sys
import types

from lifemate.asr import ChunkFormerASR


def test_chunkformer_adapter_extracts_decode_text_from_segments(monkeypatch, tmp_path):
    class FakeModel:
        @classmethod
        def from_pretrained(cls, path):
            return cls()

        def endless_decode(self, **kwargs):
            return [
                {"decode": "xin chào", "start": "00:00", "end": "00:01"},
                {"decode": "thế giới", "start": "00:01", "end": "00:02"},
            ]

    monkeypatch.setitem(sys.modules, "chunkformer", types.SimpleNamespace(ChunkFormerModel=FakeModel))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"wav")

    assert ChunkFormerASR(tmp_path / "checkpoint").transcribe(audio) == "xin chào thế giới"
