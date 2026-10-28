from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .asr import ChunkFormerASR, Qwen3ASR
from .config import RuntimeConfig, seed_everything
from .data import load_catalog, read_jsonl, split_paths
from .llm import LocalQwenAgent
from .runner import run_sample


def validate_result(result: dict[str, Any]) -> None:
    required = {"id", "tool_calls", "state_hash"}
    if set(result) != required:
        raise ValueError(f"result must contain exactly {sorted(required)}")
    if not isinstance(result["id"], str) or not isinstance(result["tool_calls"], list) or not isinstance(result["state_hash"], str):
        raise ValueError("invalid result field types")


def run_dataset(
    root: Path,
    split: str,
    model_path: Path,
    asr_model_path: Path,
    output: Path,
    limit: int | None = None,
    seed: int = 0,
    quantize: bool = False,
    asr_backend: str = "chunkformer",
) -> None:
    if split not in {"train", "public_test", "private_test"}:
        raise ValueError(f"unsupported split: {split}")
    config = RuntimeConfig(model_path, asr_model_path)
    seed_everything(seed)
    data_path, catalog_path = split_paths(root, split)  # type: ignore[arg-type]
    samples = read_jsonl(data_path)
    if limit is not None:
        samples = samples[:limit]
    catalog = load_catalog(catalog_path)
    llm = LocalQwenAgent(config.model_path, config.max_new_tokens, seed, quantize=quantize)
    if asr_backend == "chunkformer":
        asr = ChunkFormerASR(config.asr_model_path)
    elif asr_backend == "qwen3":
        asr = Qwen3ASR(config.asr_model_path, max_inference_batch_size=1)
    else:
        raise ValueError(f"unsupported ASR backend: {asr_backend}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for sample in samples:
            result = run_sample(
                sample,
                split=split,
                root=root,
                catalog=catalog,
                llm=llm,
                asr=asr,
                max_steps=config.max_steps,
            )
            validate_result(result)
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "public_test", "private_test"], default="train")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--asr-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--quantize", action="store_true", help="Load the LLM with 4-bit NF4 quantization")
    parser.add_argument("--asr-backend", choices=["chunkformer", "qwen3"], default="chunkformer")
    args = parser.parse_args(argv)
    run_dataset(
        args.root,
        args.split,
        args.model,
        args.asr_model,
        args.output,
        args.limit,
        args.seed,
        args.quantize,
        args.asr_backend,
    )
