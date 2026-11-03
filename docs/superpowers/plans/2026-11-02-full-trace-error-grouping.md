# Full trace error grouping plan

**Goal:** Extend the approved evidence-based 25-sample pilot to all 300 local traces and expose the result in the existing analysis tab.

**Approach:** Read current reviewer comments, request/history/context, every model response and executed tool result. Preserve the original pilot and saved reviews. Independent disjoint sample batches produce explicit per-sample findings; integrate and check ambiguous findings against runtime contracts. No new inference, audio transcription, external writes, or pipeline changes.

## Constraints

- Bind results to the exact experiment and snapshot digest.
- One primary classification per sample; secondary findings are counted separately.
- Include successful controls and unresolved cases; do not force them into error groups.
- Separate observed errors, reference differences, policy questions, and causal hypotheses.
- Mixed trace revisions and the non-read loop barrier require explicit limits; no claim of controlled replay.
- Reviewer comments are evidence to examine, not authoritative proof; preserve all saved review payloads.

## Tasks

- [x] Capture review baseline, preserve pilot, prepare four disjoint evidence batches.
- [x] Read and classify all 275 additional samples; reconcile taxonomy and retain/revisit pilot with current comments.
- [x] Generate full JSON, CSV and report with exact coverage, evidence and review comparisons.
- [x] Validate against server loader; publish local analysis atomically, preserving the previous file.
- [x] Verify coverage/counts, review and snapshot preservation, and live browser rendering.

## Verification

Exact ID set of 300; no duplicates; valid group references; nonempty individual evidence and comment comparison; 25 pilot cases retained with provenance. Re-read SQLite payloads and snapshot digest before/after. Validate using `scripts/review_server.py:load_analysis`, run server unit tests and a read-only browser check. Keep the original report and rollback JSON.

## Rulings

- User explicitly requested the same analysis for all 300; this is an extension of the approved method and UI, not a new design. Work runs in the active data directory so the existing local UI can display it.
- Analysis-only assistance runs in independent batches under dispatching-parallel-agents. Each worker owns one findings file and cannot modify saved reviews or the snapshot.
- Windows PowerShell native stdin replaced authored Vietnamese with question marks in initial batch exports. Re-author those findings through UTF-8 apply_patch files, not shell here-strings; check exported text before publishing. Snapshot, reviews and existing live analysis were unaffected.

## Completion evidence

- All four finding files contain 69/69/69/68 unique assigned IDs, plus 25 preserved pilot records: exact coverage of 300 snapshot samples. Authored fields have no lost-Unicode question marks or replacement characters.
- Reconciled overlapping group codes into 48 groups. Primary counts: model 132, pipeline 22, reference/policy/efficiency 82, successful controls 61, unresolved 3. These are analysis classifications, not official accuracy or automatic verdict updates.
- `build_full_analysis.py` validates all records with the production `load_analysis` loader; all 300 saved review payloads and the snapshot digest compare unchanged with the start baseline.
- Server unit tests: 6 passed. Vite build passed; only scope wording and S/U filter options were added to the existing component.
- Published `review_data/error_analysis.json` atomically after preserving `review_data/error_analysis.before_full_20261102T151643Z.json`.
- Read-only live browser verification: 300 records, 48 groups, S=61, U=3; sample 1412 reasoning and 1178 evidence displayed; navigation to review 0672 worked; zero browser errors, zero write requests, all reviews unchanged.
- Artifacts: `review_data/error_grouping_full_20261102/REPORT.md`, `analysis.json`, `analysis.csv`, `priority_review.json`, `verification.json`, `browser_verification.json`. Screenshot: `logs/full-analysis-live.png`.
