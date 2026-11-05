# Oracle tools and source experiment

**Goal:** Measure the agent with gold-selected tool availability and initial source data, while preserving autonomous calls and argument generation.

**Approved scope:** The conversation authorizes implementation on a new branch from main. No forced calls, gold arguments, gold results or final state enter model inputs.

**Architecture:** Add an opt-in `--oracle-tools-source` train-only mode to the existing LangSmith runner. Preflight all selected samples before inference. Build a sorted unique tool set from label names; select initial state sections by tool app and schema x-ref apps. Source selection is at app granularity, not gold target-row selection. Keep baseline policies, tool descriptions, execution, sampling and evaluators.

**Files:** `src/lifemate/oracle.py` owns preparation; `runner.py` accepts prepared inputs; `scripts/smoke_e2e_langsmith.py` prepares inputs and records metadata; `tests/test_oracle.py` verifies boundaries; `experiments/oracle_tools_source/README.md` documents usage.

## Tasks

- [x] Write failing tests for sorted/deduplicated names, empty labels, missing/unknown/unavailable tools, initial state isolation, cross-app references and train-only validation.
- [x] Implement preparation with copied source data and no arguments/results/final-state dependencies.
- [x] Write failing runner tests proving narrowed tools, source delivery, unchanged baseline and no forced calls.
- [x] Integrate prepared inputs and a Vietnamese additive instruction; retain full catalog name mapping for historical calls.
- [x] Integrate CLI preflight and explicit experiment metadata without changing evaluation labels.
- [x] Document the 300-sample run, app-level source scope and evaluation caveats; run tests and offline preflight over the original 300 IDs.

## Review focus

Empty tool sets must not automatically add sys.ask_missing_info. Names must not reveal label order/multiplicity. Source must come from initial state, never gold tool results. History mapping must still work for excluded tools. Baseline must not accept arbitrary sample source_context fields. Evaluation keeps read calls even though supplied source may let the model skip them; report state and call accuracy separately.

## Execution record

Branch: experiment/oracle-tools-source, main 4dffca8. User's existing untracked comparison script is untouched. Baseline targeted tests: 30 passed, 3 missing-fixture failures. PydanticAI import initially blocked by missing opentelemetry._events.

Final targeted suite: 36 passed, including real SDK requests with mocked HTTP (auto/no call, auto/tool execution, empty tool set), CLI split guard and tracing handoff. Local test dependencies were installed only in ignored scratch space, with unrelated global plugins disabled. Command: `PYTHONPATH=src:.superpowers/oracle-test-deps PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYDANTIC_DISABLE_PLUGINS=__all__ python -m pytest tests/test_oracle.py tests/test_history_prompt.py tests/test_time_context.py tests/test_tool_semantics.py -q -p no:cacheprovider` (PowerShell uses semicolon in PYTHONPATH). Compile checks and git diff whitespace checks passed. Preparation succeeded on all 300 original experiment IDs. Independent read-only review found no actionable issues. No real inference, LangSmith writes, push or merge performed.
