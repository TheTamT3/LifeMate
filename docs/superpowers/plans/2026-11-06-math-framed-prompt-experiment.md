# Math Framed Prompt Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether mathematical framing improves tool argument values while holding the full-tools oracle-context experiment fixed.

**Architecture:** Add an opt-in prompt variant to the existing full-tools mode. It must reuse the existing context, history, tool registration, model, and execution path; the treatment changes only agent instructions. Use the smoke runner to create a separate LangSmith experiment and compare matched samples against the unchanged control.

**Tech Stack:** Python, PydanticAI, LangSmith, pytest.

**Spec:** `docs/superpowers/specs/2026-11-06-math-framed-prompt-experiment.md`

## Global Constraints

- No sample- or tool-specific rules, label leakage, changes to official tool logic, new validators, or automatic argument correction.
- Keep `--concurrency 32`, `--max-steps 10`, `--seed 0`, reference text, model, and all 300 IDs fixed across full runs.
- Preserve the existing `--oracle-context-full-tools` behavior so it remains a valid control.
- Treat the 30-second target as an outcome to measure, not a guarantee from client concurrency.

## Review Focus

- The treatment must expose exactly the same tool names and schemas as the control; add an assertion in Task 1.
- History and per-sample context must be byte-equivalent across arms; add an assertion in Task 1.
- Existing oracle-tools mode must retain its original prompt; add an assertion in Task 1.
- Invalid flag combinations and non-train split must fail before inference; add CLI assertions in Task 2.
- A run with incomplete or errored samples must keep them out of the matched score denominator and report them separately; cover in Task 3.

---

### Task 1: Isolate the prompt treatment

**Files:** Modify `src/lifemate/runner.py`; create `src/lifemate/math_prompt.py`; modify `tests/test_oracle.py`.

**Interfaces:** Add `MATH_FRAMED_INSTRUCTIONS` and `MATH_PROMPT_VERSION` to `math_prompt.py`. Add `math_framed_full_tools: bool = False` to `run_sample(...)`; it is mutually exclusive with `oracle_inputs` and uses the existing full-tools context path.

- [ ] Write a failing test that captures `build_agent` and `run_agent` inputs for control and treatment, asserting only `instructions` differs; compare tool names, schemas, context, history, prompt, seed, and step limit.
- [ ] Write a failing test asserting oracle-tools mode still receives `ORACLE_INSTRUCTIONS`, and conflicting treatment/oracle flags raise `ValueError`.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Implement the five-part, tool-agnostic instruction and the smallest runner switch. Do not add a model-facing reasoning-format requirement or expose labels.
- [ ] Run the focused tests; commit this independently testable prompt variant.

### Task 2: Expose a distinct experiment command

**Files:** Modify `scripts/smoke_e2e_langsmith.py`; modify `tests/test_oracle.py`; create `experiments/math_framed_full_tools/README.md`.

**Interfaces:** Add CLI flag `--math-framed-full-tools`, mutually exclusive with both existing oracle flags. Pass it through to `run_sample`. Record a distinct prompt version and mode in LangSmith metadata and result output.

- [ ] Write failing CLI tests for exclusivity, train-only scope, mode handoff, and metadata; confirm failures.
- [ ] Add the flag and metadata without changing the existing process pool or default run path.
- [ ] Document two commands using the same model and parameters: a fixed pilot ID file and the existing `experiments/oracle_tools_source/sample_ids_300.txt`, each with `--concurrency 32 --max-steps 10 --seed 0 --use-reference-text` and a unique experiment name.
- [ ] Run focused tests and CLI help; commit the command and documentation.

### Task 3: Evaluate before any adoption

**Files:** Create `experiments/math_framed_full_tools/pilot_sample_ids.txt`; create `experiments/math_framed_full_tools/compare.py`; test `tests/test_math_prompt_compare.py`; update the experiment README.

**Interfaces:** `compare.py` reads two experiment exports keyed by sample ID and writes a Markdown/JSON summary. It must report matched sample count, missing/errors by arm, paired accuracy transitions, argument-error transitions, latency p50/p95/>30s, and tokens when available. It must not change review labels or production logic.

- [ ] Freeze a pilot panel with both previously wrong-argument and previously correct samples; save the selection method and IDs before running treatment inference.
- [ ] Write failing tests with synthetic paired exports covering improvement, regression, missing output, error, and absent latency/token fields; confirm failures.
- [ ] Implement the comparison and verify tests pass.
- [ ] Run the pilot on the server; inspect paired traces and report accuracy, regressions, latency, and token usage. Run the fixed 300 only if the pilot has no serious regression or latency blow-up; otherwise report the pilot and revise the hypothesis rather than silently changing other variables.
- [ ] Run focused tests, `git diff --check`, and review the exact prompt diff; commit the evaluator and pilot protocol.
