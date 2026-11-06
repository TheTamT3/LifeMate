# Full tools with the oracle prompt and context

This train-only experiment changes tool availability relative to `experiment/oracle-tools-source` at `e7d72c9`. The previous arm exposes the sorted unique tool names in the label. This arm exposes every tool allowed by the sample's `installed_apps`, plus the catalogued `sys.ask_missing_info`, using the existing `allowed_tools` function. It never reads the label to select tools.

Both arms use the same `ORACLE_INSTRUCTIONS`, original context without `installed_apps`, current user request, conversation history, model settings, evaluator, 10-step limit, seed, and 300 sample IDs. Tool schemas and ordering follow the selected tool set. The oracle wording says the tools were selected for the request; in the full-tools arm this sentence is inaccurate, but it remains unchanged to isolate the tool-set change. Interpret differences with that limitation in mind.

## Server command

Run after pulling this branch on the server, from `/workspace/LifeMate`. Use the same running vLLM model and LangSmith environment as the oracle run. The script creates a distinct experiment and runs **32 independent sample workers concurrently**:

```bash
PYTHONPATH=src python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --sample-ids-file experiments/oracle_tools_source/sample_ids_300.txt \
  --model models/qwen3.5-4b \
  --use-reference-text \
  --oracle-context-full-tools \
  --concurrency 32 \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --dataset-name lifemate-validation300-train \
  --experiment-name "lifemate-full-tools-oracle-context-300-$(date +%Y%m%d-%H%M%S)" \
  --max-steps 10 \
  --seed 0 > full-tools-oracle-context-300.json
```

The smoke script's default is sequential; `--concurrency 32` activates the separate worker processes. Inference throughput still depends on vLLM's server configuration. The old oracle experiment's metadata may say `concurrency=32`; check how that run was launched before treating this as a tool-only comparison. Concurrent scheduling can change latency or generated outputs even with the same seed.

For analysis, compare the same sample IDs in both experiments, report `state_hash_match` and `tool_call_accuracy` separately, and count runtime errors and missing root outputs. The full-tools run exposes the actual tool names per sample in `full_tools_oracle_context.tool_names`; LangSmith project metadata marks `oracle_context_full_tools=true` and `tool_selection=installed_apps`.
