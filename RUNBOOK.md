# LifeMate offline baseline runbook

## Local preparation

Place the Qwen3-4B checkpoint and the `khanhld/chunkformer-ctc-large-vie` checkpoint in local directories. Install the pinned dependencies from `requirements.txt`. No model download or network request is allowed during inference.

## Run one sample

```powershell
$env:PYTHONPATH = "src"
python baseline.py --root .\train+public_test\train+public_test --split train --model C:\models\qwen3-4b --asr-model C:\models\chunkformer-ctc-large-vie --output .\result\train.jsonl --limit 1
```

For public audio, use `--split public_test`; the runner invokes the local ASR adapter. The train split may use its supplied `audio_text` for development.

## Offline and reproducible operation

Keep model loading local-only, use deterministic decoding and a fixed `--seed`. The runner creates exactly one official `ToolEnv` for each sample and obtains both `tool_calls` and `state_hash` from that environment. It never reads `state.json` directly. Output is UTF-8 JSONL with one object containing `id`, `tool_calls`, and `state_hash` per line.

Measure wall time on organiser-like hardware; a sample must finish within 30 seconds. The real checkpoint smoke command should be run once for a train sample and once for a public sample after local weights are prepared.
