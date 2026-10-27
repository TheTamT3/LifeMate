# LifeMate Offline Tool-Calling Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible offline baseline that converts Vietnamese audio requests into accurate installed-tool calls and emits the organiser-compatible `id`, `tool_calls`, and `state_hash` for every sample.

**Architecture:** A split-aware runner loads JSONL samples and the matching tool catalog, transcribes audio with the local `khanhld/chunkformer-ctc-large-vie` adapter, filters tools from `context.installed_apps`, and asks a local Qwen3-4B model through a PydanticAI-compatible structured interface for calls. Each sample gets exactly one official `ToolEnv`; validated calls are executed through it, bounded multi-step observations are returned to the model, and the environment supplies the final calls and state hash.

**Tech Stack:** Python 3.10+, PyTorch, Transformers, `chunkformer`, Qwen3-4B, PydanticAI, official `zaic_tools`, pytest.

**Spec:** `SOLUTION_DESIGN.md` (plus `train+public_test/train+public_test/EVALUATION_CRITERIA.md` and the split README).

## Global Constraints

- The whole system must have fewer than 6B parameters; the LLM must have fewer than 5B parameters and context length at most 16,384 tokens.
- Inference is fully offline: no OpenAI, ElevenLabs, hosted model, network request, or external API.
- The agent must not read, copy, parse, or modify any `<split>_environment/state.json`; all app state access goes through `zaic_tools.ToolEnv`.
- Create exactly one `ToolEnv` per sample, and every environment call must appear in the submitted `tool_calls`.
- Use only tools present in `context.installed_apps`; schemas and descriptions come from the matching `<split>_tools_catalog.json`.
- Use deterministic decoding (`do_sample=False`, temperature `0`, fixed seeds for Python, NumPy, and PyTorch).
- Keep processing within 30 seconds per sample on the organiser hardware; timeout or execution failure scores zero.
- Do not use Few-shot prompting or labels generated from public/private test data in this baseline.
- Preserve Vietnamese text as UTF-8 and write JSONL with `ensure_ascii=False`.
- The final result is one JSON object per line with `id`, `tool_calls`, and `state_hash`.

## Review Focus

- A sample with no applicable action must yield `tool_calls: []` and still use the environment-derived hash; test this in the runner task.
- A tool listed in the catalog but absent from `installed_apps` must never be called; test this in filtering and execution tasks.
- Malformed, fenced, or non-array model output must not create a call; test this in the parser task.
- Unknown IDs and dependent actions must support a bounded query-then-action sequence without inventing identifiers; test this in the orchestration task.
- Unicode Vietnamese accents, JSON escaping, and stable output ordering must survive round-trip serialization; test this in the I/O task.

---

### Task 1: Establish testable project interfaces and deterministic configuration

**Files:**
- Create: `src/lifemate/__init__.py`
- Create: `src/lifemate/config.py`
- Create: `tests/test_config.py`
- Modify: `requirements.txt` (create if absent)

**Interfaces:**
- Produces `RuntimeConfig(model_path: Path, asr_model_path: Path, max_steps: int = 8, max_new_tokens: int = 512)`.
- Produces `seed_everything(seed: int) -> None`.

- [ ] **Step 1: Write failing tests** for default `max_steps == 8`, deterministic seed calls, and rejection of a model context length above 16,384.
- [ ] **Step 2: Run `pytest tests/test_config.py -v`** and verify the new interfaces fail before implementation.
- [ ] **Step 3: Implement the config dataclass and seed helper** with explicit integer validation and no network/model loading.
- [ ] **Step 4: Add pinned runtime dependencies** for Transformers/PyTorch, PydanticAI, chunkformer, and pytest without adding hosted-service SDKs.
- [ ] **Step 5: Run `pytest tests/test_config.py -v`** and verify PASS.
- [ ] **Step 6: Commit** with `feat: add deterministic baseline configuration`.

### Task 2: Implement split-aware dataset, catalog, and installed-app filtering

**Files:**
- Create: `src/lifemate/data.py`
- Create: `tests/test_data.py`
- Modify: `baseline.py` to import the new helpers instead of duplicating parsing logic.

**Interfaces:**
- `read_jsonl(path: Path) -> list[dict[str, Any]]`.
- `load_catalog(path: Path) -> dict[str, dict[str, Any]]`.
- `allowed_tools(sample: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]`.
- `split_paths(root: Path, split: Literal["train", "public_test", "private_test"]) -> tuple[Path, Path]`.

- [ ] **Step 1: Write failing tests** for UTF-8 Vietnamese JSONL, catalog flattening, missing catalog names, duplicate installed-app entries, and empty `installed_apps`.
- [ ] **Step 2: Run `pytest tests/test_data.py -v`** and verify failure.
- [ ] **Step 3: Implement the helpers** using only the sample JSON and catalog; never inspect environment directories or `state.json`.
- [ ] **Step 4: Add tests asserting that returned tool definitions retain exact official names, kinds, descriptions, and parameter schemas.**
- [ ] **Step 5: Run `pytest tests/test_data.py -v`** and verify PASS.
- [ ] **Step 6: Commit** with `feat: load split data and filter installed tools`.

### Task 3: Add offline Vietnamese ASR adapter

**Files:**
- Create: `src/lifemate/asr.py`
- Create: `tests/test_asr.py`
- Modify: `baseline.py` to use the adapter for public/private samples and retain `audio_text` only as a train-dev fallback.

**Interfaces:**
- `class ASR(Protocol): transcribe(audio_path: Path) -> str`.
- `ChunkFormerASR(model_path: Path, device: str = "auto")`.
- `ChunkFormerASR.transcribe(audio_path: Path) -> str`.
- `transcript(sample: dict[str, Any], asr: ASR | None) -> str`.

- [ ] **Step 1: Write failing tests** with a fake ASR for a sample containing audio, a train sample containing `audio_text`, missing audio, and Unicode transcript preservation.
- [ ] **Step 2: Run `pytest tests/test_asr.py -v`** and verify failure.
- [ ] **Step 3: Implement lazy local loading** of `khanhld/chunkformer-ctc-large-vie`; use local-only files, deterministic inference, expected sample rate conversion, and no network fallback.
- [ ] **Step 4: Implement `transcript()`** so `audio_text` is used only when present, while public/private samples always go through local ASR.
- [ ] **Step 5: Run the tests with the fake adapter**, then run one real local-model smoke test when the checkpoint is available.
- [ ] **Step 6: Commit** with `feat: add offline Vietnamese ASR adapter`.

### Task 4: Define prompt, call schema, parser, and PydanticAI model adapter

**Files:**
- Create: `src/lifemate/agent_schema.py`
- Create: `src/lifemate/prompting.py`
- Create: `src/lifemate/llm.py`
- Create: `tests/test_prompting.py`
- Create: `tests/test_parser.py`

**Interfaces:**
- `class ToolCall(BaseModel): name: str; arguments: dict[str, Any]`.
- `build_prompt(sample, transcript, tools, observations) -> str`.
- `parse_calls(raw: str, allowed_names: set[str]) -> list[ToolCall]`.
- `class LocalQwenAgent: generate(prompt: str) -> str`.

- [ ] **Step 1: Write failing parser tests** for a clean JSON array, fenced JSON, surrounding prose, invalid JSON, wrong argument type, unknown tool, and `[]`.
- [ ] **Step 2: Run `pytest tests/test_parser.py -v`** and verify failure.
- [ ] **Step 3: Implement strict Pydantic validation** that keeps only exact allowed names and object arguments; malformed output becomes `[]` and never reaches `ToolEnv`.
- [ ] **Step 4: Write failing prompt tests** asserting the prompt contains the Vietnamese request, history, installed context, exact schemas, prior observations, and the no-Few-shot rules.
- [ ] **Step 5: Implement `build_prompt()`** with compact catalog schemas and explicit output contract: JSON array only, exact names, no invented IDs, `[]` if no action.
- [ ] **Step 6: Implement `LocalQwenAgent`** around local Qwen3-4B Transformers generation, greedy decoding, fixed seed, local-only loading, and a PydanticAI boundary for the structured result; do not call a remote provider.
- [ ] **Step 7: Run both test files** and verify PASS with a fake model; run a one-prompt local Qwen smoke test when weights are available.
- [ ] **Step 8: Commit** with `feat: add validated local LLM tool-call interface`.

### Task 5: Implement one-sample ToolEnv orchestration and bounded multi-step execution

**Files:**
- Create: `src/lifemate/runner.py`
- Create: `tests/test_runner.py`
- Modify: `baseline.py` to delegate sample execution to `run_sample()`.

**Interfaces:**
- `run_sample(sample, split, root, catalog, llm, asr=None, max_steps=8) -> dict[str, Any]`.
- `run_sample()` returns exactly `{"id": str, "tool_calls": list[dict], "state_hash": str}`.

- [ ] **Step 1: Write failing tests** with a fake `ToolEnv` and fake LLM for a no-op sample, one write call, rejected unavailable tool, and query-then-action using an observation from the previous call.
- [ ] **Step 2: Run `pytest tests/test_runner.py -v`** and verify failure.
- [ ] **Step 3: Implement exactly one `ToolEnv(split, sample["id"], root=...)` per sample** and never import/read environment state directly.
- [ ] **Step 4: Execute only parsed allowed calls** through `env.call(name, arguments)`, append returned observations, and stop on no calls, no progress, non-read-only continuation, or eight iterations.
- [ ] **Step 5: Return `env.get_tool_calls()` and `env.get_state_hash()`** rather than reconstructing either value in agent code.
- [ ] **Step 6: Run `pytest tests/test_runner.py -v`** and verify PASS, including the exact-one-environment assertion.
- [ ] **Step 7: Commit** with `feat: execute validated calls through ToolEnv`.

### Task 6: Build the JSONL CLI and submission writer

**Files:**
- Create: `src/lifemate/cli.py`
- Create: `tests/test_cli.py`
- Modify: `baseline.py` to be a thin compatibility entry point calling `lifemate.cli.main()`.

**Interfaces:**
- `run_dataset(root: Path, split: str, model_path: Path, asr_model_path: Path, output: Path, limit: int | None = None) -> None`.
- CLI options: `--root`, `--split`, `--model`, `--asr-model`, `--output`, optional `--limit`, `--seed`.

- [ ] **Step 1: Write failing CLI tests** for train/public split filename resolution, one JSON object per line, UTF-8 output, limit handling, and required-field validation.
- [ ] **Step 2: Run `pytest tests/test_cli.py -v`** and verify failure.
- [ ] **Step 3: Implement dataset iteration** with one shared model/ASR instance but one `ToolEnv` per sample; create the output parent directory and write `ensure_ascii=False` JSONL.
- [ ] **Step 4: Add private-test-compatible split handling** without requiring private files to exist during development.
- [ ] **Step 5: Run CLI tests** and verify PASS.
- [ ] **Step 6: Commit** with `feat: add reproducible submission CLI`.

### Task 7: Add evaluation smoke checks and runtime documentation

**Files:**
- Create: `tests/test_integration.py`
- Create: `requirements.txt` or update it with exact tested versions.
- Modify: `SOLUTION_DESIGN.md` only if an implementation detail differs from the documented design.
- Create: `RUNBOOK.md`

**Interfaces:**
- Smoke command: `python baseline.py --root ... --split train --model ... --asr-model ... --output ... --limit 1`.

- [ ] **Step 1: Write integration tests** using fake ASR/LLM/ToolEnv to assert output keys, state hash passthrough, no direct `state.json` reads, and deterministic repeated results.
- [ ] **Step 2: Run the full suite** with `pytest -q` and verify PASS.
- [ ] **Step 3: Run the real local LLM/ASR smoke test** on one train sample and one public sample when the model weights are available; verify output JSONL is parseable and each line has the three required fields.
- [ ] **Step 4: Measure per-sample wall time** and fail the smoke script if it exceeds the 30-second target; document model placement, cache preparation, and offline operation in `RUNBOOK.md`.
- [ ] **Step 5: Commit** with `chore: verify offline baseline runtime`.
