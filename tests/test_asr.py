from pathlib import Path

import pytest

from lifemate.asr import transcript


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
