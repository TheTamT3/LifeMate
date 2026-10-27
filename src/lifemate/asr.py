from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ASR(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


class ChunkFormerASR:
    """Lazy, local-only adapter for the ChunkFormer Vietnamese checkpoint."""

    def __init__(self, model_path: Path, device: str = "auto") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self._pipeline: Any | None = None

    def _load(self) -> Any:
        if self._pipeline is None:
            from chunkformer import ChunkFormerModel

            self._pipeline = ChunkFormerModel.from_pretrained(str(self.model_path))
        return self._pipeline

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        result = self._load().endless_decode(
            audio_path=str(audio_path),
            chunk_size=64,
            left_context_size=128,
            right_context_size=128,
            total_batch_duration=14400,
        )
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()


def transcript(sample: dict[str, Any], asr: ASR | None) -> str:
    if "audio_text" in sample:
        return str(sample["audio_text"])
    if asr is None:
        raise ValueError(f"{sample.get('id', '<unknown>')} requires a local ASR adapter")
    audio = sample.get("audio")
    if not audio:
        raise ValueError(f"{sample.get('id', '<unknown>')} has no audio path")
    return asr.transcribe(Path(audio))
