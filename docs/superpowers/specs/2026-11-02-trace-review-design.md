# Local trace review

Approved direction: React UI with a Python backend on localhost, one reviewer, 300 samples from merged experiment 5d88ade9-1411-4032-9252-81b441078d5c. User approved implementation directly after iterating a working mockup.

Three tabs: overview, sample review, comments. Review has searchable/filterable sample navigation, audio playback, audio text, full conversation and context, side-by-side executed calls/reference calls, raw and parsed model calls, chronological LLM reasoning and tool results, evaluator notes, complete reference. Distinguish each LLM response from the last response. Missing reasoning/tokens are explicitly unavailable. Sticky review panel supports verdict, status, multiple causes, comments and step references. Save/next at trace end. Overview separates automatic scores from manual verdicts and shows latency median/p95 and >30s. Comments support search/filter and opening sample.

Immutable imported snapshot and dataset labels remain separate from SQLite reviewer state. UI rebuild/restart must preserve review. Save errors keep edits visible. Warn before leaving unsaved changes. Store per experiment/sample, timestamp and revision for concurrent-tab conflicts. Export JSON and sample IDs; backup SQLite through its backup API. Never write LangSmith or rerun inference. Audio paths restricted to dataset audio directory; bind only loopback.

Approaches considered: Streamlit (quicker, limited layout) and React/Python (chosen for flexible dense comparison and interaction). Builder choice: standard-library HTTP backend, SQLite, Vite React frontend; no additional Python framework required. Source snapshot stays in logs and is imported into ignored review_data; no credentials shipped to browser. Existing mockup reviews can be imported explicitly from the old localStorage origin via pasted JSON; automatic cross-origin transfer is unavailable. Review does not mutate labels or infer reviewer conclusions.

Non-goals: multiuser authentication, inference, LangSmith synchronization, automatic root-cause judgments. Keep working offline after import, except external trace links.
