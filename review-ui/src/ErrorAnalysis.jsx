import React, { useEffect, useState } from "react";
import "./analysis.css";
import Investigation from "./Investigation";

function Json({ value }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}
function args(value) {
  try { return typeof value === "string" ? JSON.parse(value) : value; }
  catch { return value; }
}
const belongs = (r, id) => r.primary_group === id || r.secondary_groups.includes(id);
const layerNames = { M: "Hành vi model", P: "Pipeline", D: "Reference & tiêu chí", S: "Đối chứng phù hợp", U: "Chưa kết luận" };
const feedbackNames = { unreviewed: "Chưa đối chiếu", agree: "Đồng ý", disagree: "Không đồng ý", needs_check: "Cần kiểm tra thêm" };
const emptyFeedback = { status: "unreviewed", note: "", revision: 0 };
const causeNames = { pipeline: "Nghi do pipeline dừng sớm", model: "Nghi do model · có thể kèm lỗi pipeline", insufficient: "Chưa đủ bằng chứng", not_p01: "Không thuộc P01", uninvestigated: "Chưa điều tra" };

export default function ErrorAnalysis({ reviews, total, onOpenSample, saving, onData, selection }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [layer, setLayer] = useState("");
  const [query, setQuery] = useState("");
  const [priorityOnly, setPriorityOnly] = useState(false);
  const [groupId, setGroupId] = useState("P01");
  const [sampleId, setSampleId] = useState("train_0672");
  const [cause, setCause] = useState(null);
  const [feedbackFilter, setFeedbackFilter] = useState("");
  const [drafts, setDrafts] = useState({});
  const [pending, setPending] = useState({});
  const [messages, setMessages] = useState({});
  useEffect(() => { setCause(null); }, [groupId, selection, priorityOnly, feedbackFilter, layer, query]);
  useEffect(() => { onData?.(error ? null : data); }, [data, error, onData]);
  useEffect(() => {
    if (!selection) return;
    setGroupId(selection.groupId); setPriorityOnly(false); setFeedbackFilter(""); setLayer(""); setQuery(""); setSampleId("");
  }, [selection]);
  useEffect(() => {
    const warn = e => { if (Object.keys(drafts).length || Object.values(pending).some(Boolean)) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [drafts, pending]);
  async function saveFeedback(sid) {
    if (pending[sid] || !drafts[sid]) return;
    const draft = drafts[sid];
    setPending(v => ({ ...v, [sid]: true }));
    setMessages(v => ({ ...v, [sid]: "Đang lưu…" }));
    try {
      const response = await fetch("/api/analysis-feedback/" + sid, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...draft, analysis_key: data.feedback_key }) });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || response.statusText);
      setData(v => ({ ...v, analysis_feedback: { ...v.analysis_feedback, [sid]: result } }));
      setDrafts(v => { const next = { ...v }; delete next[sid]; return next; });
      setMessages(v => ({ ...v, [sid]: "Đã lưu đối chiếu vào SQLite." }));
    } catch (e) { setMessages(v => ({ ...v, [sid]: "Chưa lưu: " + e.message })); }
    finally { setPending(v => ({ ...v, [sid]: false })); }
  }
  useEffect(() => {
    const controller = new AbortController();
    setError(""); setData(undefined);
    fetch("/api/analysis", { signal: controller.signal })
      .then(async response => {
        const value = await response.json();
        if (!response.ok) throw Error(value.error || response.statusText);
        return value;
      })
      .then(setData)
      .catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [attempt]);
  if (error) return <main className="wide"><h1>Phân tích lỗi</h1><div className="error" role="alert">Không tải được phân tích: {error}</div><p>Kiểm tra file error_analysis.json trong thư mục dữ liệu đang chạy; file phải thuộc đúng experiment và snapshot.</p><button onClick={() => setAttempt(x => x + 1)}>Thử tải lại</button></main>;
  if (data === undefined) return <main className="wide" role="status">Đang tải phân tích…</main>;
  if (data === null) return <main className="wide"><h1>Phân tích lỗi</h1><p>Chưa có dữ liệu phân nhóm. Đặt file phân tích đã duyệt tại error_analysis.json trong thư mục dữ liệu đang chạy.</p><button onClick={() => setAttempt(x => x + 1)}>Thử tải lại</button></main>;

  const q = query.trim().toLocaleLowerCase();
  const priorityIds = new Set(data.priority_review_ids || []);
  const feedbacks = data.analysis_feedback || {};
  const scopeRecords = data.records.filter(r => !priorityOnly || priorityIds.has(r.sample_id));
  const scoped = scopeRecords.filter(r => !feedbackFilter || (feedbacks[r.sample_id]?.status || "unreviewed") === feedbackFilter);
  const searchSample = r => (r.sample_id + " " + r.question + " " + r.subtype).toLocaleLowerCase().includes(q);
  const searchGroup = (id, g) => (id + " " + g.name).toLocaleLowerCase().includes(q);
  const groups = Object.entries(data.groups).filter(([id, g]) =>
    scoped.some(r => belongs(r, id)) && (!layer || id.startsWith(layer)) && (!q || searchGroup(id, g) || scoped.some(r => belongs(r, id) && searchSample(r))));
  const selectedGroup = groupId === "" ? undefined : groups.find(([id]) => id === groupId) || groups[0];
  const gid = selectedGroup?.[0], group = selectedGroup?.[1];
  const related = gid ? scoped.filter(r => belongs(r, gid)) : scoped.filter(r => !layer || r.primary_group.startsWith(layer) || r.secondary_groups.some(g => g.startsWith(layer)));
  const searched = related.filter(r => !q || (group && searchGroup(gid, group)) || searchSample(r));
  const scopedCauses = data.group_causes?.[groupId];
  const activeCauseNames = scopedCauses ? { ...scopedCauses.names, uninvestigated: "Chưa điều tra trong nhóm này" } : causeNames;
  const causeOf = r => scopedCauses ? (scopedCauses.samples[r.sample_id] || "uninvestigated") : (data.investigations?.[r.sample_id]?.conclusion || "uninvestigated");
  const causeCounts = Object.entries(activeCauseNames).map(([id, name]) => [id, name, searched.filter(r => causeOf(r) === id).length]).filter(([, , count]) => count).sort((a, b) => b[2] - a[2]);
  const visible = cause === null ? [] : searched.filter(r => cause === "" || causeOf(r) === cause);
  const record = visible.find(r => r.sample_id === sampleId) || visible[0];
  const current = record ? reviews[record.sample_id] : undefined;
  const captured = record?.existing_review;
  const sid = record?.sample_id;
  const feedbackDraft = drafts[sid] || feedbacks[sid] || emptyFeedback;
  const changeFeedback = patch => {
    setDrafts(v => ({ ...v, [sid]: { ...(v[sid] || feedbacks[sid] || emptyFeedback), ...patch } }));
    setMessages(v => ({ ...v, [sid]: "Có thay đổi chưa lưu." }));
  };
  const revisions = new Set(data.records.map(r => r.trace_revision).filter(Boolean));

  return <div className="analysis">
    <div className="analysis-panelhead">
      <label><input type="checkbox" checked={priorityOnly} disabled={!priorityIds.size} onChange={e => { setPriorityOnly(e.target.checked); setLayer(""); setQuery(""); setGroupId(""); setSampleId(""); }} /> Cần đối chiếu comment cũ ({priorityIds.size})</label>
      {priorityOnly && <p>Danh sách đề xuất xem lại nhận định cũ; không tự thay verdict hoặc comment. Đang hiển thị {visible.length} / {priorityIds.size} sample.</p>}
      <p>Đã đối chiếu: {scopeRecords.filter(r => ["agree", "disagree"].includes(feedbacks[r.sample_id]?.status)).length} / {scopeRecords.length} · Cần kiểm tra thêm: {scopeRecords.filter(r => feedbacks[r.sample_id]?.status === "needs_check").length} · Bản nháp chưa lưu: {Object.keys(drafts).length}</p>
      <label>Lọc trạng thái đối chiếu <select aria-label="Lọc trạng thái đối chiếu" value={feedbackFilter} onChange={e => { setFeedbackFilter(e.target.value); setGroupId(""); setSampleId(""); }}><option value="">Tất cả trạng thái</option>{Object.entries(feedbackNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
      <button onClick={() => { setGroupId(""); setLayer(""); setQuery(""); setSampleId(""); }}>Xem tất cả sample trong phạm vi lọc</button>
    </div>
    <div className="analysis-banner">{data.scope === "full" ? "PHÂN TÍCH TOÀN BỘ" : "PHÂN TÍCH THỬ"} · {data.records.length} sample · Đối chiếu nhận định được lưu riêng với verdict và comment review.</div>
    <div className="analysis-intro"><div><h1>Agent lệch ở bước nào?</h1><p className="analysis-muted">Từ mẫu lỗi → sample → bằng chứng. Tách hành vi model, pipeline và tiêu chí đánh giá.</p></div><div className="analysis-kpis"><div><b>{data.records.length} / {total}</b><small>Phạm vi phân tích</small></div><div><b>{Object.keys(data.groups).length}</b><small>Mẫu phân loại</small></div><div><b>{revisions.size}</b><small>Phiên bản trace</small></div></div></div>
    <main className="analysis-layout">
      <aside className="analysis-panel"><div className="analysis-panelhead"><h2>Nhóm phân tích</h2><select aria-label="Lọc lớp phân tích" value={layer} onChange={e => setLayer(e.target.value)}><option value="">Tất cả các lớp</option><option value="M">Hành vi model</option><option value="P">Pipeline</option><option value="D">Reference & tiêu chí</option><option value="S">Đối chứng phù hợp</option><option value="U">Chưa kết luận</option></select><input aria-label="Tìm nhóm hoặc sample" placeholder="Tìm nhóm / sample / nội dung…" value={query} onChange={e => setQuery(e.target.value)} /></div><div className="analysis-list">{groups.length ? groups.map(([id, g]) => <button key={id} data-analysis-group={id} aria-pressed={id === gid} className={id === gid ? "selected" : ""} onClick={() => { setGroupId(id); setSampleId(""); }}><span className="analysis-count">{scoped.filter(r => belongs(r, id)).length}</span><b>{id}</b><span className="analysis-groupname">{g.name}</span><small>{layerNames[id[0]] || g.layer}</small></button>) : <p className="analysis-empty">Không tìm thấy nhóm phù hợp.</p>}</div><p className="analysis-footnote">Số bên cạnh nhóm gồm cả sample có nhóm phụ. Một sample có thể xuất hiện ở nhiều nhóm.</p></aside>
      <section className="analysis-panel"><div className="analysis-panelhead"><h2>{group?.name || "Tất cả nhóm trong phạm vi lọc"}</h2><p>{group?.definition}</p>{group && <span className="analysis-badge green">{related.length} liên quan · {related.filter(r => r.primary_group === gid).length} nhóm chính</span>}</div>
        <div className="analysis-panelhead">
          <h3>Nhóm nguyên nhân / giả thuyết</h3>
          <p>Dựa trên kết luận điều tra đã lưu, chưa mặc định được xác nhận bằng replay. Có {searched.length} sample liên quan trong bộ lọc, gồm cả nhóm chính và nhóm phụ.</p>
          {cause === null ? <div className="cause-list">
            {causeCounts.map(([id, name, count]) => <button key={id} data-cause={id} onClick={() => { setCause(id); setSampleId(""); }}><span>{name}</span><b>{count}</b></button>)}
            <button data-cause="all" onClick={() => { setCause(""); setSampleId(""); }}><span>Xem tất cả sample liên quan</span><b>{searched.length}</b></button>
          </div> : <>
            <button onClick={() => setCause(null)}>Quay lại nhóm nguyên nhân</button>
            <p><strong>{cause === "" ? "Tất cả nguyên nhân" : activeCauseNames[cause]}</strong> · {visible.length} sample</p>
          </>}
        </div>
        <div className="analysis-list">{visible.map(r => <button key={r.sample_id} data-analysis-sample={r.sample_id} aria-pressed={r.sample_id === record?.sample_id} className={r.sample_id === record?.sample_id ? "selected" : ""} onClick={() => setSampleId(r.sample_id)}><strong>{r.sample_id}</strong><span className={"analysis-badge " + ((!gid || r.primary_group === gid) ? "green" : "blue")}>{(!gid || r.primary_group === gid) ? "Nhóm chính" : "Nhóm phụ"}</span><p>{r.question}</p><small>{r.subtype}</small><span className="analysis-badge">rev {r.trace_revision || "Không rõ"}</span></button>)}</div><p className="analysis-footnote">Comment/verdict hiện tại và nhận định thử được hiển thị riêng.</p></section>
      <section className="analysis-panel analysis-detail" aria-live="polite">{!record ? <p className="analysis-empty">{cause === null ? "Chọn nhóm nguyên nhân / giả thuyết để xem các sample." : "Không có sample phù hợp bộ lọc."}</p> : <>
        <div className="analysis-row"><div><small>CHI TIẾT SAMPLE</small><h2>{record.sample_id}</h2></div><button className="primary" disabled={saving} onClick={() => onOpenSample(record.sample_id)}>Mở trong Review sample →</button></div>
        <span className="analysis-badge">Code {record.trace_revision || "Không rõ"}</span>
        <div className="analysis-question">{record.question}</div><span className="analysis-badge blue">{record.primary_group} · {record.subtype}</span>{record.secondary_groups.map(g => <span className="analysis-badge" key={g}>Phụ: {g}</span>)}
        <div className="analysis-pair"><div className="analysis-box"><div className="analysis-label">Review hiện tại · SQLite</div><b>{current?.verdict || "Chưa có review"}</b><div className="analysis-comment">{current?.comment || "Chưa có comment."}</div><details><summary>Review được dùng khi phân nhóm</summary><p>{captured?.verdict || "Không ghi nhận"}</p><div className="analysis-comment">{captured?.comment || "Không có comment"}</div></details></div><div className="analysis-box analysis-note"><div className="analysis-label">Nhận định phân nhóm thử</div><b>{record.assessment}</b><p>{record.comparison_with_existing_comment}</p><span className="analysis-badge amber">Không thay đổi review</span></div></div>
        <div className="analysis-box analysis-evidence"><div className="analysis-label">Điểm lệch & bằng chứng</div><p>{record.evidence_summary}</p></div>
        <div className="analysis-box analysis-feedback">
          <h3>Đối chiếu nhận định phân nhóm</h3>
          <p>Đồng ý / không đồng ý với nhận định phân nhóm ở trên. Verdict và comment review giữ riêng. Bạn có thể sửa và lưu lại bất cứ lúc nào.</p>
          <label>Trạng thái đối chiếu <select aria-label="Trạng thái đối chiếu" disabled={pending[sid]} value={feedbackDraft.status} onChange={e => changeFeedback({status:e.target.value})}>{Object.entries(feedbackNames).map(([key,name]) => <option value={key} key={key}>{name}</option>)}</select></label>
          <label>Ghi chú đối chiếu <textarea aria-label="Ghi chú đối chiếu" rows={4} disabled={pending[sid]} value={feedbackDraft.note} onChange={e => changeFeedback({note:e.target.value})} /></label>
          <button className="primary" disabled={!drafts[sid] || pending[sid] || !data.feedback_key} onClick={() => saveFeedback(sid)}>Lưu đối chiếu</button>
          <button disabled={!drafts[sid] || pending[sid]} onClick={() => { if (confirm("Bỏ bản nháp đối chiếu của sample này?")) { setDrafts(v => { const next={...v}; delete next[sid]; return next; }); setMessages(v=>({...v,[sid]:"Đã bỏ bản nháp."})); } }}>Bỏ bản nháp</button>
          <p role="status">{messages[sid] || (feedbacks[sid] ? "Đã lưu: " + feedbackNames[feedbacks[sid].status] : "Chưa có đối chiếu được lưu.")}</p>
          {feedbacks[sid]?.updated_at && <small>Lưu lần cuối: {new Date(feedbacks[sid].updated_at).toLocaleString("vi-VN")}</small>}
        </div>
        <div className="analysis-box"><div className="analysis-label">Nguyên nhân & giới hạn kết luận</div><p>{record.cause_and_limits}</p><span className="analysis-badge amber">{record.confidence}</span></div>
        <div className="analysis-pair"><div><h3>Tool call thực thi</h3><Json value={record.recorded_root_output?.tool_calls || []} /></div><div><h3>Reference</h3><Json value={record.reference_calls || []} /></div></div>
        <h3>Đọc sâu bằng chứng</h3>
        {(record.llm_evidence || []).map((n, i) => <details key={n.id}><summary>Lượt {i + 1} · reasoning & raw tool call</summary><small>Node {n.id}</small>{(n.parts || []).map((p, j) => p.part_kind === "tool-call" ? <div key={j}><b>{p.tool_name}</b><Json value={args(p.args)} /></div> : <p className="analysis-reasoning" key={j}>{p.content}</p>)}</details>)}
        <details><summary>Kết quả các tool thực thi ({record.executed_tools?.length || 0})</summary>{(record.executed_tools || []).map(t => <div key={t.id}><b>{t.name}</b><Json value={t.outputs} /></div>)}</details>
        <details><summary>Conversation trước yêu cầu hiện tại</summary>{(record.history || []).map((h, i) => <div className="analysis-box" key={i}><div className="analysis-label">{h.role}</div><p>{h.audio_text || h.text}</p>{h.tool_calls && <Json value={h.tool_calls} />}{h.tool_results && <Json value={h.tool_results} />}</div>)}</details>
        <details><summary>Context của sample</summary><Json value={record.context} /></details>
        <p className="analysis-muted">Root duration: {typeof record.duration_seconds === "number" ? record.duration_seconds.toFixed(2) + " giây" : "Không có dữ liệu"} · {record.duration_seconds > 30 ? "Vượt 30 giây" : ""}</p><small>Root trace: {record.root_id}</small>
      </>}
        <div hidden={!sid}><Investigation sid={sid} analysisKey={data.feedback_key} saved={data.investigations} onSave={(sample, result) => setData(v => ({ ...v, investigations: { ...v.investigations, [sample]: result } }))} /></div>
      </section>
    </main>
  </div>;
}
