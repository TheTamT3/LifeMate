from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from ..asr import ChunkFormerASR
from .evaluator import evaluate_dataset


@dataclass(frozen=True)
class DecodeConfig:
    chunk_size: int
    left_context_size: int
    right_context_size: int

    @property
    def name(self) -> str:
        return f"chunk{self.chunk_size}_left{self.left_context_size}_right{self.right_context_size}"


def default_grid() -> list[DecodeConfig]:
    """Small, interpretable grid around the model's documented baseline."""
    return [
        DecodeConfig(64, 128, 128),
        DecodeConfig(32, 128, 128),
        DecodeConfig(96, 128, 128),
        DecodeConfig(64, 64, 64),
        DecodeConfig(64, 256, 256),
    ]


def run_sweep(
    root: Path,
    split: str,
    asr_model: Path,
    output_dir: Path,
    report: Path,
    *,
    limit: int | None = 100,
    device: str = "auto",
    batch_size: int = 1,
    configs: list[DecodeConfig] | None = None,
) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for config in configs or default_grid():
        recognizer = ChunkFormerASR(
            asr_model,
            device=device,
            chunk_size=config.chunk_size,
            left_context_size=config.left_context_size,
            right_context_size=config.right_context_size,
        )
        result = evaluate_dataset(
            root,
            split,
            asr_model,
            output_dir / f"{config.name}_predictions.jsonl",
            output_dir / f"{config.name}_report.json",
            limit=limit,
            device=device,
            batch_size=batch_size,
            asr=recognizer,
        )
        results.append({"config": config.name, **result})
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark ChunkFormer decode parameters")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--asr-model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args(argv)
    results = run_sweep(
        args.root,
        args.split,
        args.asr_model,
        args.output_dir,
        args.report,
        limit=args.limit,
        device=args.device,
        batch_size=args.batch_size,
    )
    best = min(results, key=lambda item: float(item["average_relaxed_wer"]))
    print(f"Best config: {best['config']} (relaxed WER={float(best['average_relaxed_wer']):.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
