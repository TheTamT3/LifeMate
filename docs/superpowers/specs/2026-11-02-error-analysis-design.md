# Error analysis in the local review UI

Approved: user approved the interactive mockup on port 8767 and authorized integration into the existing UI on port 8765.

Add a read-only “Phân tích lỗi” tab using the existing React/Vite and Python server. Match the mockup's three columns: groups, affected samples, evidence. Start with the 25-sample pilot and its 17 groups; label these counts as pilot scope, not rates for 300 samples. Count primary and related samples separately. Preserve uncertainty, trace revisions, and distinctions between model, pipeline, and evaluation differences.

Approaches: integrate a native React tab (chosen, consistent navigation and current reviews); embed the standalone mockup (rejected, stale comments and disconnected navigation); replace the review interface (unnecessary). No new dependencies.

Read analysis from `review_data/error_analysis.json`, outside SQLite. GET `/api/analysis` validates experiment, snapshot SHA256, group references and sample IDs. Missing analysis gives an empty state; invalid/foreign analysis produces an actionable error without breaking review. A new component owns analysis filters and selection. It reads current review props for current comments/verdicts and labels the pilot's captured review separately. A button uses the existing sample-selection handler, retaining unsaved-change and in-flight save protections.

Analysis does not change reviews, pipeline, labels, or LangSmith. No analysis write endpoint. Show reasoning/raw calls, actual execution results, history/context, prediction/reference side by side. Render all trace text through React escaping. Handle empty filters and failed loading. Pilot data remains local/ignored, so a fresh checkout without it must still review normally.

Deliverable: build and start the updated local server, verify navigation and review preservation, and document the data location and limitations. Do not automatically commit or push.
