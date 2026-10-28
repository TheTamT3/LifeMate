# ASR Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng CLI đánh giá ChunkFormer ASR độc lập trên train audio/transcript, có WER/CER/exact-match/latency, JSONL chi tiết và report tổng hợp.

**Architecture:** Đóng gói toàn bộ logic trong package con `src/lifemate/asr_eval/`, tách metric thuần Python khỏi evaluator đọc dataset và khỏi CLI. Evaluator chạy local/offline với một ASR instance dùng chung, mặc định xử lý tuần tự; `--batch-size` nhóm input và gọi capability `transcribe_batch` nếu có, còn adapter mặc định fallback tuần tự để giữ an toàn bộ nhớ và tính đúng đắn.

**Tech Stack:** Python 3.10+, pathlib, json, Unicode NFC, pytest, adapter `ChunkFormerASR` hiện có; không thêm hosted-service SDK hoặc dependency metric bắt buộc.

**Spec:** `docs/superpowers/specs/2026-10-28-asr-evaluation-design.md`

## Global Constraints

- Đánh giá phải chạy offline với checkpoint ASR local.
- Input là `train/<split>.jsonl`; transcript chuẩn lấy từ `audio_text`.
- Không gọi LLM, PydanticAI, `ToolEnv` hoặc API ngoài.
- Ghi JSON UTF-8 với `ensure_ascii=False`.
- Metric tính trên Unicode NFC, whitespace đã gom và trim; giữ cả raw text.
- `--batch-size` mặc định `1`; batch không được thay đổi kết quả so với tuần tự.

## Review Focus

- Audio path tương đối phải resolve đúng theo thư mục split; test trong Task 2.
- Transcript tiếng Việt có dấu/Unicode NFC và whitespace khác nhau; test trong Task 1.
- Transcript rỗng và prediction rỗng/không rỗng không được gây chia cho 0; test trong Task 1.
- Một audio lỗi không làm mất các dòng đã xử lý và phải làm CLI trả mã lỗi khác 0; test trong Task 2.
- Batch lớn hơn 1 phải giữ thứ tự/id và fallback tuần tự khi adapter không có batch API; test trong Task 3.

### Task 1: Implement ASR normalization and metrics

**Files:**
- Create: `src/lifemate/asr_eval/__init__.py`
- Create: `src/lifemate/asr_eval/metrics.py`
- Create: `tests/test_asr_eval_metrics.py`

**Interfaces:**
- Produces `lifemate.asr_eval.metrics.normalize_text(text: str) -> str`.
- Produces `lifemate.asr_eval.metrics.edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int`.
- Produces `lifemate.asr_eval.metrics.wer(reference: str, hypothesis: str) -> float`.
- Produces `lifemate.asr_eval.metrics.cer(reference: str, hypothesis: str) -> float`.
- Produces `lifemate.asr_eval.metrics.transcript_metrics(reference: str, prediction: str) -> dict[str, object]` with normalized strings, `wer`, `cer`, and `exact_match`.

- [ ] **Step 1: Write failing tests** for NFC normalization, repeated whitespace, WER substitutions/insertions/deletions, CER, exact match, and both empty-reference cases.
- [ ] **Step 2: Run `pytest tests/test_asr_eval_metrics.py -v`** and verify the new tests fail because the module/functions do not exist.
- [ ] **Step 3: Implement the metric functions** with an in-module dynamic-programming edit distance and explicit empty-reference handling; do not lowercase or remove Vietnamese diacritics.
- [ ] **Step 4: Run `pytest tests/test_asr_eval_metrics.py -v`** and verify all metric tests pass.
- [ ] **Step 5: Commit** with `feat: add ASR evaluation metrics`.

### Task 2: Implement dataset evaluator and JSON outputs

**Files:**
- Create: `src/lifemate/asr_eval/evaluator.py`
- Create: `tests/test_asr_eval_evaluator.py`
- Modify: `src/lifemate/asr.py` only if a shared batch protocol/helper is needed

**Interfaces:**
- Consumes `read_jsonl`, `split_paths`, `ChunkFormerASR`, and Task 1 metric functions.
- Produces `lifemate.asr_eval.evaluator.evaluate_dataset(root: Path, split: str, asr_model: Path, output: Path, report: Path, limit: int | None = None, device: str = "auto", batch_size: int = 1, seed: int = 0, asr: ASR | None = None) -> dict[str, object]`.
- Produces per-line fields `id`, `audio`, `reference`, `prediction`, normalized fields, `wer`, `cer`, `exact_match`, `latency_seconds`, and `error`.
- Produces report fields `total_samples`, `successful_samples`, `failed_samples`, `average_wer`, `average_cer`, `exact_match_rate`, `average_latency_seconds`, `p95_latency_seconds`, `input`, `model`, `output`.

- [ ] **Step 1: Write failing tests** using a fake ASR for relative audio resolution, `limit`, output UTF-8, required per-sample fields, report aggregation, and a failing audio that is recorded without dropping earlier results.
- [ ] **Step 2: Run `pytest tests/test_asr_eval_evaluator.py -v`** and verify failure on missing evaluator functions.
- [ ] **Step 3: Implement `evaluate_dataset`**: load samples, resolve `sample["audio"]` relative to `root / split`, reuse one ASR instance, time each transcription, call Task 1 metrics, write JSONL incrementally, and compute report values from successful samples only.
- [ ] **Step 4: Implement p95 deterministically** using sorted successful latencies and a documented nearest-rank/index rule; write report with UTF-8 and create parent directories.
- [ ] **Step 5: Run `pytest tests/test_asr_eval_evaluator.py -v`** and verify all evaluator tests pass.
- [ ] **Step 6: Commit** with `feat: add offline ASR dataset evaluator`.

### Task 3: Add optional batch scheduling and CLI entry point

**Files:**
- Modify: `src/lifemate/asr.py`
- Create: `src/lifemate/asr_eval/cli.py`
- Create: `asr_eval.py`
- Modify: `tests/test_asr_eval_evaluator.py`

**Interfaces:**
- Optional adapter method: `transcribe_batch(audio_paths: Sequence[Path]) -> list[str]`.
- CLI options: `--root`, `--split` (default `train`), `--asr-model`, `--output`, `--report`, `--limit`, `--device` (default `auto`), `--batch-size` (default `1`), and `--seed` (default `0`).

- [ ] **Step 1: Write failing tests** for `batch_size=1`, batch grouping with a fake adapter implementing `transcribe_batch`, preservation of input order/IDs, and fallback to per-file `transcribe` when batch capability is absent.
- [ ] **Step 2: Run `pytest tests/test_asr_eval_evaluator.py -v`** and verify batch tests fail before implementation.
- [ ] **Step 3: Add a safe `ChunkFormerASR.transcribe_batch` fallback** that preserves order and calls the existing single-audio method; keep the adapter lazy and local-only.
- [ ] **Step 4: Update `lifemate.asr_eval.evaluator.evaluate_dataset`** to process bounded groups, use `transcribe_batch` when available, fall back to sequential calls on unsupported adapters or batch exceptions, and preserve per-sample latency/error fields.
- [ ] **Step 5: Implement `lifemate.asr_eval.cli.main()`** and add `asr_eval.py` compatibility entry point that adds `src` to `sys.path` and invokes the package CLI.
- [ ] **Step 6: Run `pytest tests/test_asr_eval_evaluator.py -v` and the full `pytest -q`**; verify batch size 1 and fallback results match sequential output.
- [ ] **Step 7: Commit** with `feat: add ASR evaluation CLI and optional batching`.

### Task 4: Document local usage and verify with a real model

**Files:**
- Modify: `RUNBOOK.md`

- [ ] **Step 1: Add local commands** for a one-sample smoke test, full train evaluation, and optional `--batch-size` usage with a local checkpoint path.
- [ ] **Step 2: Document output files, metric meanings, and that batch size 1 is the safe default for limited VRAM.**
- [ ] **Step 3: Run a real one-sample local command** with the available ChunkFormer checkpoint; verify JSONL/report parse as UTF-8 and contain the required fields.
- [ ] **Step 4: Run the full test suite and record the actual local smoke-test command/result** in the handoff; do not claim full-dataset success if model/data are unavailable.
- [ ] **Step 5: Commit** with `docs: document local ASR evaluation workflow`.
