# Oracle tools and initial app sources

Branch: `experiment/oracle-tools-source`, based on `main` at `4dffca8`.

This train-only experiment measures performance with the correct tool set and relevant initial app data supplied in advance. The agent still chooses whether to call a tool, which tool, arguments, ordering, repetitions and when to finish. No call is forced; the SDK retains automatic tool choice.

## Input contract

- Tool availability is the **sorted unique set** of `label.tool_calls[*].name`. Label ordering and multiplicity are discarded. No extra system tool is added; an empty gold set exposes no tools.
- `source_context` contains **initial state sections of relevant apps**, selected from each tool's catalog `app` and recursively discovered schema `x-ref` app prefixes. The state comes from `train/train_environment/<id>/state.json` before any tool execution. Metadata and unrelated apps are excluded. Stateless tools may have no state section.
- Selection is at **app granularity**, not exact target-row granularity. All rows of a selected app remain available, so entity selection and ambiguity resolution are still tested. This does not establish an upper bound with perfect target-record selection.
- Gold arguments, gold tool results and final state are never used to construct the agent input. Historical conversation remains unchanged, including wire names for tools excluded from the current tool set.
- The current user message is JSON with `request` and `source_context`. Baseline system policies, tool semantics, schemas, sampling, thinking and request limit stay unchanged; one Vietnamese instruction explains the supplied sources and autonomous tool choice.
- The baseline path is unchanged when the flag is absent. All selected oracle inputs are prepared before model inference or experiment creation; malformed labels and unknown/unavailable tools fail preflight.

## Run the same 300 samples

`sample_ids_300.txt` contains the 300 root sample IDs from local `logs/experiment_5efb0ae0_results.json` (experiment `5efb0ae0-b8f5-4ecd-b53f-eb271863878c`). It selects the complete experiment, without applying the opaque UI filter from the original link.

Use the server's existing Python/vLLM environment, LangSmith configuration and matching model alias:

```bash
PYTHONPATH=src python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --sample-ids-file experiments/oracle_tools_source/sample_ids_300.txt \
  --model models/qwen3.5-4b \
  --use-reference-text \
  --oracle-tools-source \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --dataset-name lifemate-validation300-train \
  --experiment-name "lifemate-oracle-tools-source-300-$(date +%Y%m%d-%H%M%S)" \
  --max-steps 10 \
  --seed 0 > oracle-tools-source-300.json
```

For local preparation, the original data root is `train+public_test/train+public_test`. For a baseline comparison, use the same command without `--oracle-tools-source` and a distinct experiment name. `--use-reference-text` removes ASR variability; keep it identical between runs.

## Evaluation

Keep the existing evaluator and labels. Report `state_hash_match` and `tool_call_accuracy` separately: supplied initial source data can let the agent skip a gold read call, producing the correct state but a lower full-call-set match. Do not silently remove reads or rewrite labels. Runtime failures and latency should also be reported.

Project metadata records `oracle_tools_source`, `oracle_version`, tool/source selection and automatic tool choice. Each successful sample output records selected tool names and source app names. Do not interpret this label-assisted result as normal benchmark performance.

Offline preparation succeeded for all 300 IDs: 21 samples with no gold tools; tool-set size distribution `{0: 21, 1: 76, 2: 89, 3: 63, 4: 38, 5: 13}`. This is preparation validation, not measured LLM accuracy. No real model inference has been run for this experiment yet.

Verification: 36 targeted tests passed, including real SDK requests over mocked HTTP, autonomous tool execution/omission, an empty tool set, label isolation, CLI restrictions and tracing handoff. Three pre-existing policy tests on main require the absent `tests/fixtures/mechanism_cases.json`; these were already failing before this change.
