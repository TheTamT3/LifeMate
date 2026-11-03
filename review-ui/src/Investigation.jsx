import React, { useEffect, useState } from "react";

const conclusions = { uninvestigated: "Chưa điều tra", pipeline: "Nghi do pipeline", model: "Nghi do model", not_p01: "Không thuộc P01", insufficient: "Chưa đủ bằng chứng" };
const replays = { not_run: "Chưa chạy", confirmed: "Xác nhận giả thuyết", refuted: "Bác bỏ giả thuyết", inconclusive: "Chưa kết luận" };
const empty = { conclusion: "uninvestigated", evidence: "", replay: "not_run", replay_notes: "", revision: 0 };

// Keep this component mounted when changing samples so unsaved notes survive navigation.
export default function Investigation({ sid, analysisKey, saved = {}, onSave }) {
  const [drafts, setDrafts] = useState({});
  const [pending, setPending] = useState({});
  const [messages, setMessages] = useState({});
  const key = analysisKey + ":" + sid;
  const value = drafts[key] || saved[sid] || empty;
  useEffect(() => {
    const warn = e => { if (Object.keys(drafts).length || Object.values(pending).some(Boolean)) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [drafts, pending]);
  const change = patch => {
    setDrafts(v => ({ ...v, [key]: { ...(v[key] || saved[sid] || empty), ...patch } }));
    setMessages(v => ({ ...v, [key]: "Có thay đổi chưa lưu." }));
  };
  async function save() {
    if (!drafts[key] || pending[key]) return;
    const sample = sid, draftKey = key;
    setPending(v => ({ ...v, [draftKey]: true }));
    try {
      const response = await fetch("/api/investigation/" + sample, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...drafts[draftKey], analysis_key: analysisKey }) });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || response.statusText);
      onSave(sample, result);
      setDrafts(v => { const next = { ...v }; delete next[draftKey]; return next; });
      setMessages(v => ({ ...v, [draftKey]: "Đã lưu điều tra vào SQLite." }));
    } catch (e) { setMessages(v => ({ ...v, [draftKey]: "Chưa lưu: " + e.message })); }
    finally { setPending(v => ({ ...v, [draftKey]: false })); }
  }
  return <section className="analysis-box analysis-feedback" aria-label="Điều tra nguyên nhân">
    <h3>Điều tra nguyên nhân</h3>
    <p>Ghi giả thuyết và bằng chứng riêng với đối chiếu, comment và verdict. Kết luận từ trace chưa phải xác nhận bằng replay.</p>
    <label>Kết luận nguyên nhân <select aria-label="Kết luận nguyên nhân" disabled={pending[key]} value={value.conclusion} onChange={e => change({ conclusion: e.target.value })}>{Object.entries(conclusions).map(([k, name]) => <option key={k} value={k}>{name}</option>)}</select></label>
    <label>Bằng chứng điều tra <textarea aria-label="Bằng chứng điều tra" rows={5} disabled={pending[key]} value={value.evidence} placeholder="Việc còn thiếu; tool cuối và kết quả; điểm dừng trace; model có được gọi tiếp không…" onChange={e => change({ evidence: e.target.value })} /></label>
    <label>Trạng thái replay <select aria-label="Trạng thái replay" disabled={pending[key]} value={value.replay} onChange={e => change({ replay: e.target.value })}>{Object.entries(replays).map(([k, name]) => <option key={k} value={k}>{name}</option>)}</select></label>
    <label>Chi tiết replay <textarea aria-label="Chi tiết replay" rows={3} disabled={pending[key]} value={value.replay_notes} placeholder="Giả thuyết được kiểm tra, điều kiện chạy, kết quả và đường dẫn bằng chứng…" onChange={e => change({ replay_notes: e.target.value })} /></label>
    <button className="primary" disabled={!drafts[key] || pending[key] || !analysisKey} onClick={save}>Lưu điều tra</button>
    <button disabled={!drafts[key] || pending[key]} onClick={() => { if (confirm("Bỏ bản nháp điều tra của sample này?")) { setDrafts(v => { const next = { ...v }; delete next[key]; return next; }); setMessages(v => ({ ...v, [key]: "Đã bỏ bản nháp." })); } }}>Bỏ bản nháp điều tra</button>
    <p role="status">{messages[key] || (saved[sid] ? "Đã lưu: " + conclusions[saved[sid].conclusion] : "Chưa có điều tra được lưu.")}</p>
    <small>Bản nháp điều tra chưa lưu: {Object.keys(drafts).length}{saved[sid]?.updated_at ? " · Lưu lần cuối: " + new Date(saved[sid].updated_at).toLocaleString("vi-VN") : ""}</small>
  </section>;
}
