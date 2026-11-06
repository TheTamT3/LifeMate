# Math Framed Prompt Experiment

## Purpose

Test whether a short mathematical framing improves LifeMate tool argument selection. This is a prompt experiment, not a symbolic solver or a change to tool execution.

## Design

Use the existing full-tools oracle-context experiment as the control. In the treatment, change only the agent instruction. Keep the same model, thinking settings, sample context, conversation history, user request, installed-app tool set and schemas, evaluator, sample IDs, seed, 10-request limit, and client concurrency of 32. Record the exact prompt version in run metadata. Do not alter `ORACLE_INSTRUCTIONS` or the existing control mode.

The control instruction says the tools were selected for the request, which is inaccurate with full installed-app tools. The treatment removes that premise while adding mathematical framing. Any observed difference is therefore attributable to the complete instruction change, not proven to arise from mathematical framing alone.

The treatment instruction has five short parts: (1) a one-sentence role, (2) the current goal, (3) known facts and unknown values, (4) constraints that each candidate argument must satisfy, and (5) the next action and a check of tool results. The instruction asks the model to use facts from the request, context, history, and tool results, and to look up or ask when a required value remains unresolved. It must not require a visible chain of thought, extra tool calls, or a fixed sequence of actions. Tool calls remain the output of interest.

The wording must be general across tools and unseen test schemas. It must not mention sample IDs, gold labels, or specific app-tool behaviors. It must not add a computational validator, replace argument values in code, or modify the official tool package.

## Evaluation

First run a small preregistered panel containing argument-error cases and previously correct cases from the same validation set. Keep the panel list fixed before comparing results. Then run the existing 300 IDs if the pilot has no serious regression or latency blow-up. Compare only samples with completed outputs in both arms, and separately report missing outputs and errors. Report tool-call accuracy, state-hash match, argument-error transitions, latency, request and token usage, and the count of formerly correct samples that regress. Inspect matched traces to distinguish value-selection improvements from unrelated tool-selection changes. A prompt-only improvement is a measured result, not an assumption.

## Operational limit

The deployment goal remains under 30 seconds per sample. Client concurrency 32 does not guarantee that target if vLLM queues requests. Report per-sample latency distribution, especially p50, p95, and the number above 30 seconds.
