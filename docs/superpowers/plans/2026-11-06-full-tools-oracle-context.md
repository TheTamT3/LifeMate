# Full Tools with Oracle Prompt Implementation Plan

**Goal:** Compare full installed-app tools against oracle-selected tools while keeping the oracle prompt, sample context, model settings, and sample IDs fixed. Run 32 independent sample workers concurrently on the server.

**Architecture:** Keep the existing oracle mode. Add a separate train experiment mode that uses the same oracle prompt and context construction with `allowed_tools(sample, catalog)`. Parallelize the smoke runner with process workers because its current per-sample tracing temporarily wraps runner functions and is not thread-safe.

**Tech Stack:** Python, PydanticAI, LangSmith, pytest.

**Baseline:** `experiment/oracle-tools-source` at `e7d72c9`.

## Tasks

- [x] Add a runner test showing full tools are exposed while the model receives the same instructions, context, user prompt, and history as oracle mode; implement the smallest mode switch in `src/lifemate/runner.py`.
- [x] Add CLI tests for mutually exclusive experiment modes, positive concurrency, and 32-worker dispatch; implement the full-tools flag and process worker in `scripts/smoke_e2e_langsmith.py`.
- [x] Document the exact server command, same 300 sample IDs, metadata, comparison limits, and `--concurrency 32` in `experiments/full_tools_oracle_context/README.md`.
- [x] Run focused tests and the available full test suite; verify CLI help, diff, and branch state. Do not run model inference locally. The full suite is blocked by four existing import errors; the available subset has three existing missing-fixture failures. The focused non-SDK tests pass; the three SDK tests need the pinned local OpenTelemetry dependency.

## Comparison constraint

The oracle instruction says the available tools were selected for the task. Keeping that wording exactly fixed makes it misleading in the full-tools arm. This is a known experimental limitation and must be disclosed with results. Concurrency changes execution scheduling relative to any sequential oracle run; pairwise accuracy comparisons should account for that.
