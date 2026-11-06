# Math-framed prompt with full tools

This train-only experiment tests the general mathematical framing in `src/lifemate/math_prompt.py`. It uses the same installed-app tools and the same context construction as `--oracle-context-full-tools`. Only the agent instruction changes. The prompt asks the model to identify the current goal, known and missing values, constraints on each argument, and the next action. It does not add a code solver, tool-specific rules, or argument correction.

The control's oracle instruction says the available tools were selected for the request; with full tools this premise is inaccurate. The treatment also removes that premise, so a score difference cannot be attributed solely to mathematical framing.

## Fixed pilot

`pilot_sample_ids.txt` contains 20 IDs from the existing 300-ID panel. The first 10 were classified as primary argument errors and the next 10 had both automated scores equal to 1 in experiment `5efb0ae0`; these are **historical strata**, not the outcomes of the current full-tools control. This fixed panel is an early regression screen and is not an unbiased accuracy estimate.

Run both commands on the same server, with the same running model and LangSmith environment. Both use 32 independent sample workers. A vLLM server configured with `--max-num-seqs 1` can still queue requests.

```bash
PYTHONPATH=src python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 --split train \
  --sample-ids-file experiments/math_framed_full_tools/pilot_sample_ids.txt \
  --model models/qwen3.5-4b --use-reference-text \
  --oracle-context-full-tools --concurrency 32 \
  --llm-base-url http://127.0.0.1:8000/v1 --llm-model-name qwen3-4b \
  --dataset-name lifemate-validation300-train \
  --experiment-name "lifemate-full-tools-control-pilot-$(date +%Y%m%d-%H%M%S)" \
  --max-steps 10 --seed 0 > full-tools-control-pilot.json

PYTHONPATH=src python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 --split train \
  --sample-ids-file experiments/math_framed_full_tools/pilot_sample_ids.txt \
  --model models/qwen3.5-4b --use-reference-text \
  --math-framed-full-tools --concurrency 32 \
  --llm-base-url http://127.0.0.1:8000/v1 --llm-model-name qwen3-4b \
  --dataset-name lifemate-validation300-train \
  --experiment-name "lifemate-math-framed-pilot-$(date +%Y%m%d-%H%M%S)" \
  --max-steps 10 --seed 0 > math-framed-pilot.json
```

Compare completed sample outputs against train labels:

```bash
PYTHONPATH=src python -m experiments.math_framed_full_tools.compare \
  --root data/validation_300 \
  --sample-ids-file experiments/math_framed_full_tools/pilot_sample_ids.txt \
  --control full-tools-control-pilot.json --treatment math-framed-pilot.json \
  --output math-framed-pilot-comparison.json
```

The comparison reports paired tool-call and state-hash transitions, including argument mismatches where the called tool-name multiset equals the label but its arguments differ. It reports missing/error rows separately. The smoke output does not currently contain per-sample latency or tokens, so those fields will be empty unless supplied from trace exports; check LangSmith for latency and usage before deciding to scale. The comparison's argument mismatch is a mechanical measure, not a human-reviewed root-cause label.

## Full 300

After reviewing the pilot for regressions and latency, run the same two commands with `--sample-ids-file experiments/oracle_tools_source/sample_ids_300.txt` and distinct full-run experiment names. Keep all other flags identical, including `--concurrency 32`. Compare with the same script and the 300-ID file. Do not compare scores from runs with different tool sets or sample sets as a prompt-only effect.
