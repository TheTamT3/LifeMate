# Local trace review

Open http://127.0.0.1:8765 after starting:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_review.ps1
```

First start installs/builds React and imports `logs/merge_experiments_snapshot.json`, joining sample labels/audio from `train+public_test/train+public_test/train`. Python server requires only the standard library. Node/npm is needed for builds. Subsequent starts work offline.

Use Overview / Review sample / Comments. Review status is explicit: select **Đã review** when finished, then save. Step note buttons insert a stable node ID into the comment. Filter samples by tool, text, status, automatic mismatch, latency or runtime error. Comments have separate verdict/cause filters. Export JSON, agent-error sample IDs, or download a consistent SQLite backup from Overview.

Durable files: `review_data/snapshot.json` (imported traces/labels) and `review_data/reviews.sqlite` (manual reviews). Both are ignored by git. Back up SQLite before moving machines; restore only while server is stopped. Rebuilding UI does not touch either. Reimporting the source refreshes snapshot but preserves reviews. No LangSmith writes and no inference.

This workspace is scoped to the merged experiment above. The importer rejects unrelated experiment sources to avoid attaching existing reviews to a different experiment's sample IDs.

After UI changes: `npm.cmd run build --prefix review-ui`, then refresh browser. Keep the server port and URL consistent. Mockup localStorage belongs to the earlier prototype URL and is not migrated automatically; copy any important prototype notes manually before retiring it.

Save failures retain current edits; stale saves from another tab return a conflict. A browser warning protects unsaved edits on closing, and changing sample asks before discarding. There is no automatic saving. Reasoning is only what was recorded; zero token telemetry may mean missing instrumentation. Latency is root trace duration from two source runs. Backend binds loopback and audio is limited to dataset's audio subtree. Do not expose this personal tool to a network.
