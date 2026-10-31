from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from ..asr import ASR, ChunkFormerASR, ParakeetASR, Qwen3ASR, WhisperASR
from ..data import read_jsonl, split_paths
from .metrics import transcript_metrics


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _base_row(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": sample.get("id"),
        "audio": sample.get("audio"),
        "reference": sample.get("audio_text"),
        "prediction": None,
        "reference_normalized": None,
        "prediction_normalized": None,
        "wer": None,
        "cer": None,
        "exact_match": None,
        "latency_seconds": None,
        "error": None,
    }


def _audio_path(root: Path, split: str, sample: dict[str, Any]) -> Path:
    audio_value = sample.get("audio")
    if not audio_value:
        raise ValueError("sample has no audio path")
    reference_value = sample.get("audio_text")
    if reference_value is None:
        raise ValueError("sample has no audio_text reference")
    path = Path(audio_value)
    resolved = path if path.is_absolute() else root / split / path
    if not resolved.exists():
        raise FileNotFoundError(f"audio file does not exist: {resolved}")
    return resolved


def evaluate_dataset(
    root: Path,
    split: str,
    asr_model: Path,
    output: Path,
    report: Path,
    limit: int | None = None,
    device: str = "auto",
    batch_size: int = 1,
    seed: int = 0,
    asr_backend: str = "chunkformer",
    asr: ASR | None = None,
) -> dict[str, object]:
    """Evaluate a local ASR against labelled transcripts in a JSONL split."""

    del seed  # Reserved for future ASR runtimes with stochastic decoding.
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    data_path, _ = split_paths(Path(root), split)  # type: ignore[arg-type]
    samples = read_jsonl(data_path)
    if limit is not None:
        samples = samples[:limit]
    if asr is not None:
        recognizer = asr
    elif asr_backend == "chunkformer":
        recognizer = ChunkFormerASR(Path(asr_model), device=device)
    elif asr_backend == "qwen3":
        recognizer = Qwen3ASR(Path(asr_model), device=device, max_inference_batch_size=batch_size)
    elif asr_backend == "whisper":
        recognizer = WhisperASR(Path(asr_model), device=device)
    elif asr_backend == "parakeet":
        recognizer = ParakeetASR(Path(asr_model), device=device)
    else:
        raise ValueError(f"unsupported ASR backend: {asr_backend}")

    output = Path(output)
    report = Path(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    successful_latencies: list[float] = []
    successful_wers: list[float] = []
    successful_cers: list[float] = []
    successful_relaxed_wers: list[float] = []
    successful_relaxed_cers: list[float] = []
    successful_fuzzy_scores: list[float] = []
    exact_matches = 0
    relaxed_exact_matches = 0
    fuzzy_matches = 0

    with output.open("w", encoding="utf-8") as handle:
        for start in range(0, len(samples), batch_size):
            group = samples[start : start + batch_size]
            group_rows: list[tuple[dict[str, Any], dict[str, Any], Path | None]] = []
            prepared: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
            for sample in group:
                row = _base_row(sample)
                try:
                    audio_path = _audio_path(Path(root), split, sample)
                    prepared.append((sample, row, audio_path))
                    group_rows.append((sample, row, audio_path))
                except Exception as exc:
                    row["error"] = str(exc)
                    group_rows.append((sample, row, None))

            if not prepared:
                for _, row, _ in group_rows:
                    rows.append(row)
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                continue

            audio_paths = [item[2] for item in prepared]
            started = time.perf_counter()
            predictions: list[str] | None = None
            batch_method = getattr(recognizer, "transcribe_batch", None)
            if batch_method is not None and batch_size > 1:
                try:
                    candidate = batch_method(audio_paths)
                    if len(candidate) == len(audio_paths):
                        predictions = [str(item) for item in candidate]
                except Exception:
                    predictions = None

            if predictions is None:
                predictions = []
                for audio_path in audio_paths:
                    try:
                        predictions.append(str(recognizer.transcribe(audio_path)))
                    except Exception as exc:
                        predictions.append("")
                        prepared[len(predictions) - 1][1]["error"] = str(exc)

            elapsed_per_sample = (time.perf_counter() - started) / len(prepared)
            for index, (sample, row, _) in enumerate(prepared):
                if row["error"] is not None:
                    continue
                prediction = predictions[index]
                metrics = transcript_metrics(str(sample["audio_text"]), prediction)
                row.update(
                    {
                        "prediction": prediction,
                        **metrics,
                        "latency_seconds": elapsed_per_sample,
                    }
                )
                successful_latencies.append(elapsed_per_sample)
                successful_wers.append(float(metrics["wer"]))
                successful_cers.append(float(metrics["cer"]))
                successful_relaxed_wers.append(float(metrics["relaxed_wer"]))
                successful_relaxed_cers.append(float(metrics["relaxed_cer"]))
                successful_fuzzy_scores.append(float(metrics["fuzzy_token_f1"]))
                exact_matches += int(bool(metrics["exact_match"]))
                relaxed_exact_matches += int(bool(metrics["relaxed_exact_match"]))
                fuzzy_matches += int(bool(metrics["fuzzy_match"]))

            for _, row, _ in group_rows:
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    successful = len(successful_latencies)
    failed = len(rows) - successful
    result: dict[str, object] = {
        "total_samples": len(rows),
        "successful_samples": successful,
        "failed_samples": failed,
        "average_wer": sum(successful_wers) / successful if successful else 0.0,
        "average_cer": sum(successful_cers) / successful if successful else 0.0,
        "exact_match_rate": exact_matches / successful if successful else 0.0,
        "average_relaxed_wer": sum(successful_relaxed_wers) / successful if successful else 0.0,
        "average_relaxed_cer": sum(successful_relaxed_cers) / successful if successful else 0.0,
        "relaxed_exact_match_rate": relaxed_exact_matches / successful if successful else 0.0,
        "average_fuzzy_token_f1": sum(successful_fuzzy_scores) / successful if successful else 0.0,
        "fuzzy_match_rate": fuzzy_matches / successful if successful else 0.0,
        "average_latency_seconds": sum(successful_latencies) / successful if successful else 0.0,
        "p95_latency_seconds": _p95(successful_latencies),
        "input": str(data_path),
        "model": str(asr_model),
        "output": str(output),
    }
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failed:
        raise RuntimeError(f"ASR evaluation completed with {failed} failed sample(s)")
    return result
