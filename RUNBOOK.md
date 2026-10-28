# LifeMate offline baseline runbook

## Local preparation

Place the Qwen3-4B checkpoint and the `khanhld/chunkformer-ctc-large-vie` checkpoint in local directories. Install the pinned dependencies from `requirements.txt`. No model download or network request is allowed during inference.

For the local NVIDIA GPU environment created for this project:

```powershell
& .\.venv-gpu\Scripts\Activate.ps1
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Use `--device cuda` for ASR. The environment uses a CUDA-enabled PyTorch build and is separate from the system Python environment.

## Run one sample

```powershell
$env:PYTHONPATH = "src"
python baseline.py --root .\train+public_test\train+public_test --split train --model C:\models\qwen3-4b --asr-model C:\models\chunkformer-ctc-large-vie --output .\result\train.jsonl --limit 1
```

For public audio, use `--split public_test`; the runner invokes the local ASR adapter. The train split may use its supplied `audio_text` for development.

## Evaluate ASR separately

The ASR evaluator uses the labelled `audio_text` in `train.jsonl` as reference and does not load Qwen, PydanticAI, or `ToolEnv`.

Run one local sample first:

```powershell
$env:PYTHONPATH = "src"
python asr_eval.py --root .\train+public_test\train+public_test --split train --asr-model C:\models\chunkformer-ctc-large-vie --output .\result\asr_predictions.jsonl --report .\result\asr_report.json --limit 1 --device auto --batch-size 1
```

Run the full train evaluation by removing `--limit 1`. `--batch-size 1` is the safe default for limited VRAM; larger values are optional and preserve sample order, with a sequential fallback when native batch decoding is unavailable. In batch mode, `latency_seconds` is the measured batch wall time divided across valid samples, so use batch size 1 when comparing per-audio latency. The prediction JSONL contains strict metrics (`wer`, `cer`, `exact_match`), relaxed metrics (`relaxed_wer`, `relaxed_cer`, `relaxed_exact_match`), and supplementary fuzzy metrics (`fuzzy_token_f1`, `fuzzy_match`); relaxed scoring lowercases, removes punctuation, and normalizes whitespace, while `fuzzy_match` is true when token F1 is at least `0.8`. The report JSON contains aggregate strict/relaxed/fuzzy metrics and latency statistics.

## Offline and reproducible operation

Keep model loading local-only, use deterministic decoding and a fixed `--seed`. The runner creates exactly one official `ToolEnv` for each sample and obtains both `tool_calls` and `state_hash` from that environment. It never reads `state.json` directly. Output is UTF-8 JSONL with one object containing `id`, `tool_calls`, and `state_hash` per line.

Measure wall time on organiser-like hardware; a sample must finish within 30 seconds. The real checkpoint smoke command should be run once for a train sample and once for a public sample after local weights are prepared.
