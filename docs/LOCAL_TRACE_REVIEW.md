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

## Phân tích lỗi

The **Phân tích lỗi** tab shows the approved pilot: 25 samples and 17 concrete patterns. Filter by model, pipeline, reference/criteria, or search by group/sample/question. Group counts include secondary memberships; they are not population error rates. Select a sample to compare the current SQLite review with the separate pilot assessment, inspect reasoning/raw calls/executed results, and open it in **Review sample** using the existing unsaved-draft guard.

Place the pilot JSON at `review_data/error_analysis.json` (or `error_analysis.json` under the server's `--data` directory). The original pilot is `review_data/error_grouping_pilot_20261102/pilot.json`. Keep these local files when moving the workspace; they are ignored by git. GET `/api/analysis` is read-only and checks experiment, the SHA256 of the exact snapshot bytes, sample IDs and group references. Missing or mismatched data displays a message in this tab without interrupting review. Re-export/revalidate analysis when the snapshot changes; do not bypass the digest check.

Current comments/verdicts come from the review UI's loaded SQLite state. The expandable “Review được dùng khi phân nhóm” is historical context from the pilot. Refresh the page to see reviews changed in another browser tab. Analysis never saves a verdict or comment. Trace revisions and uncertainty are preserved; no replay or inference is performed.

Backend changes require restarting `scripts/review_server.py` after rebuilding the frontend. UI-only changes require rebuilding and refreshing.

### Đối chiếu nhận định phân nhóm

Phân tích hiện phủ 300 sample. Tích **Cần đối chiếu comment cũ (13)** để mở danh sách đề xuất xem lại. Trong phần **Đối chiếu nhận định phân nhóm**, chọn Chưa đối chiếu / Đồng ý / Không đồng ý / Cần kiểm tra thêm, nhập ghi chú và bấm **Lưu đối chiếu**. Đồng ý hoặc Không đồng ý được tính là đã đối chiếu; Cần kiểm tra thêm vẫn được thống kê riêng. Dùng **Lọc trạng thái đối chiếu** để tiếp tục các sample còn lại.

Trạng thái này xác nhận nhận định phân nhóm, không phải verdict Agent đúng/sai. Nó không sửa verdict/comment review cũ. Muốn sửa review, mở **Review sample** và lưu riêng. Có thể mở lại đối chiếu để sửa hoặc trả về Chưa đối chiếu. Bản nháp được giữ khi chuyển sample/tab trong phiên trang hiện tại, nhưng phải lưu trước khi đóng hoặc refresh.

Feedback được lưu trong bảng SQLite `analysis_feedback`, gắn với sample và digest của bản phân tích. Nếu nội dung phân tích thay đổi, feedback cũ vẫn được giữ trong DB/export nhưng không tự áp dụng cho bản mới. Lưu từ tab đã cũ trả lỗi xung đột; sao chép ghi chú trước khi refresh. JSON export và SQLite backup bao gồm feedback. File snapshot và dữ liệu phân nhóm gốc không bị sửa bởi thao tác đối chiếu.
