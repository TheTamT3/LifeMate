# Error Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Integrate the approved analysis mockup into the existing local review UI with 25 pilot samples.

**Architecture:** A validated read-only JSON API serves the local analysis independently of SQLite reviews. A React tab consumes analysis and current review props, reusing existing sample navigation.

**Tech Stack:** Python standard library, React 19, Vite 6; existing dependencies only.

**Spec:** `docs/superpowers/specs/2026-11-02-error-analysis-design.md`

## Global Constraints

- Preserve all review payloads and immutable snapshot; no inference or LangSmith writes.
- Pilot scope is 25 samples, not population statistics; preserve revision and uncertainty.
- Missing/foreign analysis must not disrupt normal review.
- Work in the user’s current checkout to update the running local UI; test against an isolated data directory/port. No git integration requested.

## Review Focus

- Stale captured comments: render current reviews alongside labeled historical pilot context.
- Dirty drafts: use existing guarded selection; cancellation retains draft and analysis view.
- No filter matches: show explicit empty state, no stale detail.
- Foreign/stale analysis: validate experiment and snapshot digest before serving.
- Missing local pilot file: display instructions without failure in other tabs.

### Task 1: Analysis data and API

Files: `scripts/review_server.py`, `tests/test_review_server.py`, local ignored `review_data/error_analysis.json`.

- [x] Write and run failing tests for missing, valid, foreign/stale, unknown/duplicate samples, and bad groups.
- [x] Add `load_analysis(path, snapshot_bytes)` and GET `/api/analysis` with explicit invalid-data errors.
- [x] Copy the approved pilot to the fixed local data filename; retain the original pilot artifacts.
- [x] Run review-server unit tests.

### Task 2: Native analysis tab

Files: new `review-ui/src/ErrorAnalysis.jsx`, new scoped `analysis.css`, modify `App.jsx`, update `docs/LOCAL_TRACE_REVIEW.md`.

- [x] Write a browser smoke check that fails because the analysis tab does not exist.
- [x] Implement filter/group/sample/evidence panels and current-versus-captured review context.
- [x] Reuse existing guarded navigation to review; handle no matches, absent data, and API errors.
- [x] Build and verify browser navigation, reasoning, source revisions and draft preservation on disposable data.

### Task 3: Activate and verify

- [x] Inspect diff; verify API schema validation and React rendering use no review mutations.
- [x] Capture review payloads and snapshot digest before restarting the existing server.
- [x] Restart only the identified local review server, retaining its data directory.
- [x] Check live API, 25 analysis samples, 300 review payloads unchanged; inspect screenshot.
- [x] Mark completed checks and report the local UI link with pilot limitations.

## Execution ledger

Ruling: execute inline in current checkout, using a disposable server for browser tests. This task explicitly targets the running local UI and its existing ignored local pilot data. No worktree/branch changes or commits are needed.

Verification: six review-server unit tests passed, including malformed nested payload cases (observed failing before validation). The production Vite build passed. Disposable browser checks passed filters, reasoning, current-versus-captured review, dirty-draft cancel/accept, no PUT from analysis, and missing/foreign/malformed analysis handling. A reviewer identified malformed-data render risk; validation was added and re-reviewed successfully. Live port 8765 serves 25 pilot records and 17 groups; all 300 review payloads and snapshot SHA256 match the pre-restart baseline. Browser smoke on live data performed reads only.
