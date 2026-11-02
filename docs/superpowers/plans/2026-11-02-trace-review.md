# Trace review implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Review 300 imported traces locally with durable comments.
**Architecture:** Immutable JSON import, Python SQLite/API, React single-page UI served by Python after Vite build.
**Tech Stack:** Python standard library, SQLite, React, Vite.
**Spec:** docs/superpowers/specs/2026-11-02-trace-review-design.md

## Global constraints
Loopback only; no remote mutations; keep reviews separate from source; never delete existing data; single reviewer; three tabs.

## Review focus
Missing trace fields; malicious audio paths; SQLite persistence across reimport; unsaved edits and failed saves; stale revisions from another tab.

### Task 1: Import and persistence API
Files: scripts/review_server.py, tests/test_review_server.py.
Interfaces: build_snapshot(source, dataset) -> dict; ReviewStore(path).get/save(sample_id,payload); GET /api/samples, /api/sample/ID, /api/reviews, /api/overview; PUT /api/review/ID; GET /api/export, /api/backup, /api/audio/ID.
- [x] Write unittest coverage for import selection, multiple reasoning turns, missing fields, review persistence, validation, revision conflicts, audio traversal.
- [x] Run tests RED, implement import/store/API, run GREEN.

### Task 2: React review UI and launcher
Files: review-ui/package.json, src/App.jsx, src/style.css, index.html, vite.config.js; scripts/start_review.ps1; docs/LOCAL_TRACE_REVIEW.md.
Interfaces: task 1 APIs; built static files served on localhost:8765.
- [x] Implement three tabs, filtering, side-by-side JSON, chronological nodes, sticky review panel, durable save, comments, exports and backups.
- [x] Build frontend, import all300 without modifying snapshot, run API/browser smoke including save/reload on separate database.
- [x] Start actual app, verify HTTP and counts, report link and remaining limitations.

## Verification and review
5 Python unittest cases passed. Production Vite build passed. Headless Edge exercised 300-sample listing, six reasoning turns, side-by-side coordinates, step note, save/reload persistence, comments/open, sticky panel and overview with no page errors. API smoke verified 409 stale revision, valid SQLite backup and audio RIFF bytes. Independent reviewer found save-in-flight race: reproduced with failing browser assertion, fixed by locking draft/navigation while saving, then delayed-PUT regression passed. Raw disclosure renders verbatim. Import rejects source experiments outside this fixed merged workspace. Prototype localStorage notes are not auto-migrated; manually copy any desired notes. No remote changes, no inference, no production test reviews, no commit/push performed.
