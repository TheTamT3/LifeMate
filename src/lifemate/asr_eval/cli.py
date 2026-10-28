from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluator import evaluate_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a local Vietnamese ASR checkpoint")
    parser.add_argument("--root", type=Path, required=True, help="dataset root containing the split directory")
    parser.add_argument("--split", default="train")
    parser.add_argument("--asr-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--asr-backend", choices=("chunkformer", "qwen3"), default="chunkformer")
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        kwargs = dict(
            root=args.root,
            split=args.split,
            asr_model=args.asr_model,
            output=args.output,
            report=args.report,
            limit=args.limit,
            device=args.device,
            batch_size=args.batch_size,
            seed=args.seed,
        )
        if args.asr_backend != "chunkformer":
            kwargs["asr_backend"] = args.asr_backend
        result = evaluate_dataset(**kwargs)
    except RuntimeError as exc:
        print(f"ASR evaluation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Evaluated {result['successful_samples']}/{result['total_samples']} samples; "
        f"WER={result['average_wer']:.4f}, CER={result['average_cer']:.4f}"
    )
    return 0
