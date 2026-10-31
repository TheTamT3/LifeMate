from __future__ import annotations

import wave
from pathlib import Path
from collections.abc import Sequence
from typing import Any, Protocol


class ASR(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


class ChunkFormerASR:
    """Lazy, local-only adapter for the ChunkFormer Vietnamese checkpoint."""

    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        *,
        chunk_size: int = 64,
        left_context_size: int = 128,
        right_context_size: int = 128,
        total_batch_duration: int = 14400,
    ) -> None:
        self.model_path = Path(model_path)
        self.device = device
        self.chunk_size = chunk_size
        self.left_context_size = left_context_size
        self.right_context_size = right_context_size
        self.total_batch_duration = total_batch_duration
        self._pipeline: Any | None = None

    def _load(self) -> Any:
        if self._pipeline is None:
            from chunkformer import ChunkFormerModel

            self._pipeline = ChunkFormerModel.from_pretrained(str(self.model_path))
            if self.device != "auto" and hasattr(self._pipeline, "to"):
                self._pipeline = self._pipeline.to(self.device)
        return self._pipeline

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        result = self._load().endless_decode(
            audio_path=str(audio_path),
            chunk_size=self.chunk_size,
            left_context_size=self.left_context_size,
            right_context_size=self.right_context_size,
            total_batch_duration=self.total_batch_duration,
        )
        if isinstance(result, dict):
            text = result.get("text", result.get("decode", ""))
        elif isinstance(result, list):
            segments = []
            for item in result:
                if isinstance(item, dict):
                    segment = item.get("decode", item.get("text", ""))
                else:
                    segment = item
                if segment:
                    segments.append(str(segment).strip())
            text = " ".join(segments)
        else:
            text = str(result)
        return text.strip()

    def transcribe_batch(self, audio_paths: Sequence[Path]) -> list[str]:
        """Safe fallback batch API; preserves order without requiring extra VRAM."""

        return [self.transcribe(path) for path in audio_paths]


class Qwen3ASR:
    """Lazy adapter for the local Qwen3-ASR transformers backend."""

    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        *,
        language: str = "Vietnamese",
        max_inference_batch_size: int = 1,
        max_new_tokens: int = 256,
    ) -> None:
        self.model_path = Path(model_path)
        self.device = device
        self.language = language
        self.max_inference_batch_size = max_inference_batch_size
        self.max_new_tokens = max_new_tokens
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                import torch
                from qwen_asr import Qwen3ASRModel
            except ImportError as exc:
                raise RuntimeError(
                    "Qwen3-ASR requires the optional 'qwen-asr' package; install it before use"
                ) from exc

            use_cuda = self.device == "cuda" or (self.device == "auto" and torch.cuda.is_available())
            device_map = "cuda:0" if use_cuda else "cpu"
            dtype = torch.float16 if use_cuda else torch.float32
            self._model = Qwen3ASRModel.from_pretrained(
                str(self.model_path),
                dtype=dtype,
                device_map=device_map,
                max_inference_batch_size=self.max_inference_batch_size,
                max_new_tokens=self.max_new_tokens,
            )
        return self._model

    @staticmethod
    def _text(result: Any) -> str:
        if isinstance(result, (list, tuple)):
            result = result[0] if result else ""
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        return str(getattr(result, "text", result)).strip()

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        result = self._load().transcribe(audio=str(audio_path), language=self.language)
        return self._text(result)

    def transcribe_batch(self, audio_paths: Sequence[Path]) -> list[str]:
        paths = list(audio_paths)
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(path)
        if not paths:
            return []
        result = self._load().transcribe(
            audio=[str(path) for path in paths],
            language=[self.language] * len(paths),
        )
        return [self._text(item) for item in result]


class WhisperASR:
    """Lazy Transformers pipeline adapter for Whisper-family checkpoints.

    This also supports Vietnamese fine-tunes such as BuzzASR when the local
    checkpoint exposes the standard Transformers speech-sequence-to-sequence
    interface.
    """

    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        *,
        language: str = "vi",
    ) -> None:
        self.model_path = Path(model_path)
        self.device = device
        self.language = language
        self._pipeline: Any | None = None

    def _load(self) -> Any:
        if self._pipeline is None:
            try:
                import torch
                from transformers import pipeline
            except ImportError as exc:
                raise RuntimeError(
                    "Whisper ASR requires the 'transformers' and 'torch' packages"
                ) from exc

            use_cuda = self.device == "cuda" or (
                self.device == "auto" and torch.cuda.is_available()
            )
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=str(self.model_path),
                device=0 if use_cuda else -1,
                torch_dtype=torch.float16 if use_cuda else torch.float32,
            )
        return self._pipeline

    @staticmethod
    def _text(result: Any) -> str:
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        return str(getattr(result, "text", result)).strip()

    @staticmethod
    def _audio_input(audio_path: Path) -> Any:
        """Read PCM WAV without relying on an external ffmpeg executable."""

        try:
            import numpy as np

            with wave.open(str(audio_path), "rb") as handle:
                channels = handle.getnchannels()
                sample_width = handle.getsampwidth()
                sample_rate = handle.getframerate()
                frames = handle.readframes(handle.getnframes())
            if sample_width == 1:
                audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
                audio = (audio - 128.0) / 128.0
            elif sample_width == 2:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                raise ValueError(f"unsupported WAV sample width: {sample_width}")
            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1)
            return {"array": audio, "sampling_rate": sample_rate}
        except (EOFError, ImportError, OSError, ValueError, wave.Error):
            # Keep mocked/test pipelines and non-WAV Transformers inputs usable.
            return str(audio_path)

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        return self._text(
            self._load()(
                self._audio_input(audio_path),
                generate_kwargs={
                    "language": self.language,
                    "task": "transcribe",
                    "no_repeat_ngram_size": 3,
                    "repetition_penalty": 1.2,
                },
            )
        )

    def transcribe_batch(self, audio_paths: Sequence[Path]) -> list[str]:
        return [self.transcribe(path) for path in audio_paths]


class ParakeetASR:
    """Lazy NeMo adapter for Parakeet Vietnamese checkpoints."""

    def __init__(self, model_path: Path, device: str = "auto") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from nemo.collections.asr.models import ASRModel
            except ImportError as exc:
                raise RuntimeError(
                    "Parakeet ASR requires NeMo; install nemo_toolkit[asr] before use"
                ) from exc
            self._model = ASRModel.from_pretrained(model_name=str(self.model_path))
            if self.device != "auto" and hasattr(self._model, "to"):
                self._model = self._model.to(self.device)
        return self._model

    @staticmethod
    def _text(result: Any) -> str:
        if isinstance(result, (list, tuple)):
            result = result[0] if result else ""
        if isinstance(result, dict):
            return str(result.get("text", result.get("decoded_text", ""))).strip()
        return str(getattr(result, "text", result)).strip()

    def transcribe(self, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)
        result = self._load().transcribe([str(audio_path)])
        return self._text(result)

    def transcribe_batch(self, audio_paths: Sequence[Path]) -> list[str]:
        paths = list(audio_paths)
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(path)
        if not paths:
            return []
        result = self._load().transcribe([str(path) for path in paths])
        return [self._text(item) for item in result]


def transcript(sample: dict[str, Any], asr: ASR | None) -> str:
    if "audio_text" in sample:
        return str(sample["audio_text"])
    if asr is None:
        raise ValueError(f"{sample.get('id', '<unknown>')} requires a local ASR adapter")
    audio = sample.get("audio")
    if not audio:
        raise ValueError(f"{sample.get('id', '<unknown>')} has no audio path")
    return asr.transcribe(Path(audio))
