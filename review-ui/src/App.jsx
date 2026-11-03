import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import ErrorAnalysis from "./ErrorAnalysis";
const verdicts = [
  "Chưa kết luận",
  "Agent đúng",
  "Agent sai",
  "Label có vấn đề",
  "Chưa đủ dữ liệu",
];
const tags = [
  "Hiểu sai yêu cầu",
  "Sai tool",
  "Sai / bịa tham số",
  "Thiếu / thừa bước",
  "Lỗi thực thi",
  "Label / evaluator",
  "Vượt 30 giây",
];
const empty = {
  status: "unreviewed",
  verdict: "Chưa kết luận",
  tags: [],
  comment: "",
  revision: 0,
};
async function api(path, options) {
  const r = await fetch("/api/" + path, options);
  const v = await r.json();
  if (!r.ok) throw Error(v.error || r.statusText);
  return v;
}
function Json({ value }) {
  let v = value;
  if (typeof v === "string") {
    try {
      v = JSON.parse(v);
    } catch {}
  }
  return <pre>{typeof v === "string" ? v : JSON.stringify(v, null, 2)}</pre>;
}
function Details({ title, value }) {
  return (
    <details>
      <summary>{title}</summary>
      <Json value={value} />
    </details>
  );
}
function download(name, value, type = "application/json") {
  const u = URL.createObjectURL(new Blob([value], { type }));
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
function App() {
  const [analysisData, setAnalysisData] = useState(undefined);
  const [analysisSelection, setAnalysisSelection] = useState(null);
  const [items, setItems] = useState([]),
    [reviews, setReviews] = useState({}),
    [tab, setTab] = useState("review"),
    [id, setId] = useState(""),
    [sample, setSample] = useState(null),
    [draft, setDraft] = useState(empty),
    [dirty, setDirty] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [query, setQuery] = useState(""),
    [status, setStatus] = useState(""),
    [outcome, setOutcome] = useState(""),
    [verdictFilter, setVerdictFilter] = useState(""),
    [tagFilter, setTagFilter] = useState(""),
    [saving, setSaving] = useState(false);
  useEffect(() => {
    Promise.all([api("samples"), api("reviews")])
      .then(([d, r]) => {
        setItems(d.samples);
        setReviews(r);
        setId(d.samples[0]?.id || "");
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!id) return;
    let active = true;
    setSample(null);
    api("sample/" + id)
      .then((s) => {
        if (active) {
          setSample(s);
          setDraft(reviews[id] || { ...empty });
          setDirty(false);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [id]);
  useEffect(() => {
    const fn = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", fn);
    return () => window.removeEventListener("beforeunload", fn);
  }, [dirty]);
  function change(p) {
    if (saving) return;
    setDraft((d) => ({ ...d, ...p }));
    setDirty(true);
    setNotice("Chưa lưu");
  }
  function select(next) {
    if (saving) return;
    if (next === id) {
      setTab("review");
      return;
    }
    if (
      dirty &&
      !confirm("Có thay đổi chưa lưu. Bỏ thay đổi và chuyển sample?")
    )
      return;
    setId(next);
    setTab("review");
    window.scrollTo(0, 0);
  }
  async function save(next = false) {
    setSaving(true);
    setError("");
    try {
      const r = await api("review/" + id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      setReviews((v) => ({ ...v, [id]: r }));
      setDraft(r);
      setDirty(false);
      setNotice("Đã lưu vào SQLite");
      if (next) {
        const i = filtered.findIndex((s) => s.id === id);
        if (filtered[i + 1]) {
          setId(filtered[i + 1].id);
          window.scrollTo(0, 0);
        } else setNotice("Đã lưu · hết danh sách đang lọc");
      }
    } catch (e) {
      setError(e.message + " Dữ liệu đang nhập vẫn được giữ.");
    } finally {
      setSaving(false);
    }
  }
  const filtered = items.filter(
    (s) =>
      (s.id + " " + s.text + " " + s.tools.join(" "))
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (!status || (reviews[s.id]?.status || "unreviewed") === status) &&
      (!outcome ||
        (outcome === "slow"
          ? s.duration > 30
          : outcome === "error"
            ? s.error
            : s.scores.tool_call_accuracy === 0)),
  );
  const commented = items
    .filter((s) => reviews[s.id])
    .filter(
      (s) =>
        (s.id + " " + reviews[s.id].comment)
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (!verdictFilter || reviews[s.id].verdict === verdictFilter) &&
        (!tagFilter || reviews[s.id].tags.includes(tagFilter)),
    );
  const reviewed = Object.values(reviews).filter(
    (r) => r.status === "reviewed",
  ).length;
  const durations = items
    .map((s) => s.duration)
    .filter((t) => typeof t === "number")
    .sort((a, b) => a - b);
  const percentile = (p) =>
    durations.length
      ? durations[Math.max(0, Math.ceil(durations.length * p) - 1)].toFixed(2)
      : "—";
  const score = (k) => {
    const vals = items
      .map((s) => s.scores[k])
      .filter((x) => typeof x === "number");
    return vals.length
      ? ((100 * vals.reduce((a, b) => a + b, 0)) / vals.length).toFixed(2) + "%"
      : "—";
  };
  function note(n) {
    change({
      comment:
        draft.comment +
        (draft.comment ? "\n\n" : "") +
        "[" +
        n.name +
        " · " +
        n.id +
        "] ",
    });
    document.getElementById("comment")?.focus({ preventScroll: true });
  }
  const llms = sample?.nodes.filter((n) => n.run_type === "llm") || [];
  return (
    <>
      <header>
        <div>
          <b>LifeMate / Experiment review</b>
          <small>{items.length} samples · Local · SQLite</small>
        </div>
        <nav>
          {[
            ["overall", "Tổng quan"],
            ["review", "Review sample"],
            ["comments", "Nhận xét"],
            ["analysis", "Phân tích lỗi"],
          ].map(([key, label]) => (
            <button
              className={tab === key ? "active" : ""}
              key={key}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>
      {error && (
        <div className="error" role="alert">
          {error} <button onClick={() => setError("")}>Đóng</button>
        </div>
      )}
      <div hidden={tab !== "analysis"}><ErrorAnalysis reviews={reviews} total={items.length} onOpenSample={select} saving={saving} onData={setAnalysisData} selection={analysisSelection} /></div>
      {tab === "overall" && (
        <main className="wide">
          <h1>Tổng quan</h1>
          <section className="error-group-summary">
            <h2>Nhóm lỗi chi tiết · số lượng giảm dần</h2>
            <p>Đếm theo nhóm chính, mỗi sample xuất hiện một lần. Gồm hành vi model, pipeline và khác biệt reference/tiêu chí (D); nhóm D không mặc định là lỗi nghiệp vụ. Đối chứng đúng (S) và chưa kết luận (U) nằm ngoài bảng.</p>
            <small>Phân nhóm hiện hành là bản phân tích gốc; feedback đối chiếu được lưu riêng, chưa tự điều chỉnh số đếm.</small>
            {analysisData === undefined ? <p>Đang tải phân nhóm…</p> : !analysisData ? <p>Chưa có dữ liệu phân nhóm hợp lệ. Mở Phân tích lỗi để kiểm tra.</p> : (() => {
              const counts = {};
              for (const r of analysisData.records) counts[r.primary_group] = (counts[r.primary_group] || 0) + 1;
              const rows = Object.entries(analysisData.groups).filter(([id]) => /^[MPD]/.test(id) && counts[id]).sort(([a], [b]) => counts[b] - counts[a] || a.localeCompare(b));
              return <>
                <table className="error-group-table"><thead><tr><th scope="col">Mã nhóm</th><th scope="col">Nhóm lỗi chi tiết</th><th scope="col">Số sample</th></tr></thead><tbody>{rows.map(([id, g]) => <tr key={id} data-summary-group={id}><td><button onClick={() => { setAnalysisSelection({ groupId: id }); setTab("analysis"); }}>{id}</button></td><td>{g.name}</td><td>{counts[id]}</td></tr>)}</tbody></table>
                <p>Tổng trong bảng: {rows.reduce((sum, [id]) => sum + counts[id], 0)} sample · Đối chứng (S): {analysisData.records.filter(r => r.primary_group.startsWith("S")).length} · Chưa kết luận (U): {analysisData.records.filter(r => r.primary_group.startsWith("U")).length}.</p>
              </>;
            })()}
          </section>
          <div className="grid">
            <section>
              <h2>Tiến độ review</h2>
              <h1>
                {reviewed} / {items.length}
              </h1>
              <progress value={reviewed} max={items.length || 1} />
              {["unreviewed", "reviewing", "reviewed"].map((s, i) => (
                <p key={s}>
                  {["Chưa review", "Đang review", "Đã review"][i]}:{" "}
                  <button
                    onClick={() => {
                      setStatus(s);
                      setTab("review");
                    }}
                  >
                    {
                      items.filter(
                        (x) => (reviews[x.id]?.status || "unreviewed") === s,
                      ).length
                    }
                  </button>
                </p>
              ))}
            </section>
            <section>
              <h2>Điểm tự động · toàn experiment</h2>
              <p>
                State hash match: <b>{score("state_hash_match")}</b>
              </p>
              <p>
                Tool call accuracy: <b>{score("tool_call_accuracy")}</b>
              </p>
              <p>Root runtime errors: {items.filter((s) => s.error).length}</p>
              <small>Điểm tự động tách biệt với kết luận reviewer.</small>
            </section>
            <section>
              <h2>Kết luận thủ công</h2>
              {verdicts.map((v) => (
                <p key={v}>
                  {v}:{" "}
                  <button
                    onClick={() => {
                      setVerdictFilter(v);
                      setTab("comments");
                    }}
                  >
                    {
                      Object.values(reviews).filter((r) => r.verdict === v)
                        .length
                    }
                  </button>
                </p>
              ))}
            </section>
            <section>
              <h2>Thời gian root trace</h2>
              <p>
                Trung vị:{" "}
                {durations.length
                  ? (
                      (durations[Math.floor((durations.length - 1) / 2)] +
                        durations[Math.floor(durations.length / 2)]) /
                      2
                    ).toFixed(2)
                  : "—"}
                s
              </p>
              <p>p95: {percentile(0.95)}s</p>
              <p>
                Vượt 30s:{" "}
                <button
                  onClick={() => {
                    setOutcome("slow");
                    setTab("review");
                  }}
                >
                  {durations.filter((t) => t > 30).length}
                </button>{" "}
                / {durations.length}
              </p>
              <small>
                Hai nguồn chạy khác nhau; đây là thời gian pipeline đã ghi nhận.
              </small>
            </section>
            <section>
              <h2>Nguyên nhân · nhiều nhãn / sample</h2>
              {tags.map((t) => (
                <p key={t}>
                  {t}:{" "}
                  <button
                    onClick={() => {
                      setTagFilter(t);
                      setTab("comments");
                    }}
                  >
                    {
                      Object.values(reviews).filter((r) => r.tags.includes(t))
                        .length
                    }
                  </button>
                </p>
              ))}
            </section>
            <section>
              <h2>Tool theo sample đã review</h2>
              {[...new Set(items.flatMap((s) => s.tools))].map((t) => {
                const used = items.filter(
                  (s) =>
                    s.tools.includes(t) && reviews[s.id]?.status === "reviewed",
                );
                return used.length ? (
                  <p key={t}>
                    {t}:{" "}
                    {
                      used.filter((s) => reviews[s.id].verdict === "Agent sai")
                        .length
                    }{" "}
                    sai / {used.length} reviewed
                  </p>
                ) : null;
              })}
            </section>
          </div>
          <section>
            <h2>Dữ liệu review</h2>
            <button
              onClick={() =>
                download("reviews.json", JSON.stringify({ reviews }, null, 2))
              }
            >
              Xuất JSON
            </button>{" "}
            <button
              onClick={() =>
                download(
                  "rerun-sample-ids.txt",
                  Object.keys(reviews)
                    .filter((k) => reviews[k].verdict === "Agent sai")
                    .join("\n"),
                  "text/plain",
                )
              }
            >
              Xuất IDs agent sai
            </button>{" "}
            <a href="/api/backup">Sao lưu SQLite</a>
            <p>
              <small>
                Snapshot và SQLite tách biệt. Sửa UI hoặc restart không xóa
                review.
              </small>
            </p>
          </section>
        </main>
      )}
      {tab === "comments" && (
        <main className="wide">
          <h1>Nhận xét</h1>
          <div className="filters">
            <input
              placeholder="Tìm sample / comment"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
            >
              <option value="">Tất cả kết luận</option>
              {verdicts.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
            <select
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
            >
              <option value="">Tất cả nguyên nhân</option>
              {tags.map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </div>
          <section className="table">
            <table>
              <thead>
                <tr>
                  {[
                    "Sample",
                    "Kết luận",
                    "Nhãn lỗi",
                    "Comment",
                    "Cập nhật",
                    "",
                  ].map((v, i) => (
                    <th key={i}>{v}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {commented.map((s) => (
                  <tr key={s.id}>
                    <td>{s.id}</td>
                    <td>{reviews[s.id].verdict}</td>
                    <td>{reviews[s.id].tags.join(" · ")}</td>
                    <td className="comment">
                      {reviews[s.id].comment || "Chưa có comment"}
                    </td>
                    <td>
                      {new Date(reviews[s.id].updated_at).toLocaleString(
                        "vi-VN",
                      )}
                    </td>
                    <td>
                      <button onClick={() => select(s.id)}>Mở sample →</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!commented.length && <p>Chưa có review phù hợp bộ lọc.</p>}
          </section>
        </main>
      )}
      {tab === "review" && (
        <div className="shell">
          <aside className="samples">
            <h2>Samples · {filtered.length}</h2>
            <input
              placeholder="Tìm ID / text / tool"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Mọi trạng thái</option>
              <option value="unreviewed">Chưa review</option>
              <option value="reviewing">Đang review</option>
              <option value="reviewed">Đã review</option>
            </select>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            >
              <option value="">Mọi kết quả</option>
              <option value="wrong">Tool call khác label</option>
              <option value="slow">Vượt 30 giây</option>
              <option value="error">Runtime error</option>
            </select>
            {filtered.map((s) => (
              <button
                className={"sample " + (s.id === id ? "selected" : "")}
                key={s.id}
                onClick={() => select(s.id)}
              >
                <b>{s.id}</b>
                <small>{s.tools.join(" · ") || "Không gọi tool"}</small>
                <small>
                  {reviews[s.id]?.status || "unreviewed"} ·{" "}
                  {s.duration?.toFixed(2) ?? "—"}s
                </small>
              </button>
            ))}
          </aside>
          <main>
            {!sample ? (
              <p>Đang tải trace…</p>
            ) : (
              <>
                <h1>{sample.id}</h1>
                <p>
                  {sample.duration?.toFixed(2) ?? "—"}s · {llms.length} lượt LLM
                  · {sample.root.outputs?.tool_calls?.length || 0} tool calls
                </p>
                <section>
                  <h2>Yêu cầu người dùng</h2>
                  <p>{sample.sample.audio_text || "Không có audio text"}</p>
                  <audio
                    key={id}
                    controls
                    preload="none"
                    src={"/api/audio/" + id}
                  />
                  <small>
                    Nếu audio không có trên máy, trình phát sẽ báo không khả
                    dụng.
                  </small>
                  <Details
                    title="Context tại thời điểm yêu cầu"
                    value={sample.sample.context}
                  />
                  <details>
                    <summary>
                      Conversation · {sample.sample.history?.length || 0} lượt
                      lịch sử
                    </summary>
                    {sample.sample.history?.map((h, i) => (
                      <div className={"bubble " + h.role} key={i}>
                        <small>{h.role}</small>
                        <p>{h.audio_text || h.text}</p>
                        {h.tool_calls && (
                          <Details
                            title="Tool calls / kết quả trong history"
                            value={{
                              tool_calls: h.tool_calls,
                              tool_results: h.tool_results,
                            }}
                          />
                        )}
                      </div>
                    ))}
                  </details>
                </section>
                <section>
                  <h2>Dự đoán và reference</h2>
                  <div className="compare">
                    <div>
                      <h3>TOOL CALLS THỰC THI</h3>
                      <Json value={sample.root.outputs?.tool_calls || []} />
                    </div>
                    <div>
                      <h3>REFERENCE TOOL CALLS</h3>
                      <Json value={sample.sample.label?.tool_calls || []} />
                    </div>
                  </div>
                  <p>
                    Tool call accuracy:{" "}
                    {sample.root.feedback_stats?.tool_call_accuracy?.avg ?? "—"}{" "}
                    · State hash match:{" "}
                    {sample.root.feedback_stats?.state_hash_match?.avg ?? "—"}
                  </p>
                  <Details
                    title="Reference output đầy đủ"
                    value={sample.sample.label}
                  />
                  <Details
                    title="Kết quả tổng hợp pipeline & giải thích điểm tự động"
                    value={{
                      output: sample.root.outputs,
                      evaluator: sample.root.feedback_stats,
                    }}
                  />
                  {sample.root.error && <Json value={sample.root.error} />}
                </section>
                <h2>Trace theo thời gian bắt đầu</h2>
                {sample.nodes
                  .filter(
                    (n) =>
                      n.run_type === "llm" ||
                      n.name.startsWith("tool.") ||
                      n.name.includes("normalization"),
                  )
                  .map((n) => (
                    <section id={"step-" + n.id} key={n.id}>
                      <button
                        className="step-note"
                        disabled={saving}
                        onClick={() => note(n)}
                      >
                        ＋ Ghi chú bước này
                      </button>
                      <h2>
                        {n.run_type === "llm"
                          ? "LLM lượt " +
                            (llms.indexOf(n) + 1) +
                            " / " +
                            llms.length
                          : n.name}
                      </h2>
                      <small>
                        {n.start_time}{" "}
                        {n.end_time && n.start_time
                          ? " · " +
                            (
                              (new Date(n.end_time) - new Date(n.start_time)) /
                              1000
                            ).toFixed(3) +
                            "s"
                          : ""}
                      </small>
                      {n.run_type === "llm" ? (
                        <>
                          <p>
                            finish_reason:{" "}
                            {n.outputs?.response?.finish_reason || "không có"}
                          </p>
                          {!(n.outputs?.response?.parts || []).some(
                            (p) => p.part_kind === "thinking",
                          ) && <p>Không ghi nhận reasoning cho lượt này.</p>}
                          {n.outputs?.response?.parts?.map((p, i) => (
                            <div key={i}>
                              <h3>
                                {p.part_kind === "thinking"
                                  ? "REASONING"
                                  : p.part_kind === "text"
                                    ? n === llms.at(-1)
                                      ? "TEXT Ở LƯỢT LLM CUỐI"
                                      : "TEXT Ở LƯỢT NÀY · CHƯA PHẢI LƯỢT CUỐI"
                                    : p.part_kind === "tool-call"
                                      ? "TOOL CALL · " + p.tool_name
                                      : p.part_kind}
                              </h3>
                              <Json
                                value={
                                  p.part_kind === "tool-call"
                                    ? p.args
                                    : p.content
                                }
                              />
                              {p.part_kind === "tool-call" &&
                                typeof p.args === "string" && (
                                  <details>
                                    <summary>Chuỗi raw gốc</summary>
                                    <pre>{p.args}</pre>
                                  </details>
                                )}
                            </div>
                          ))}
                          <Details
                            title="Usage ghi nhận (0 có thể là thiếu telemetry)"
                            value={
                              n.outputs?.response?.usage ||
                              n.outputs?.usage_metadata
                            }
                          />
                          <Details
                            title="Messages / prompt đầu vào lượt LLM"
                            value={n.inputs?.messages}
                          />
                        </>
                      ) : (
                        <>
                          <Json value={n.inputs} />
                          <Details
                            title="Kết quả tool / sự kiện"
                            value={n.outputs}
                          />
                        </>
                      )}
                      {n.error && <Json value={n.error} />}
                    </section>
                  ))}
                <section>
                  <h2>Đã đọc hết trace</h2>
                  <button disabled={saving} onClick={() => save()}>
                    Lưu review
                  </button>{" "}
                  <button
                    className="primary"
                    disabled={saving}
                    onClick={() => save(true)}
                  >
                    Lưu & sample tiếp theo →
                  </button>
                  <p>
                    <a
                      href={
                        "https://smith.langchain.com" + sample.root.app_path
                      }
                      target="_blank"
                      rel="noreferrer"
                    >
                      Trace nguồn ↗
                    </a>
                  </p>
                </section>
              </>
            )}
          </main>
          <aside className="review">
            <fieldset disabled={saving || !sample}>
              <h2>Đánh giá của bạn</h2>
              <small>Độc lập với điểm tự động</small>
              <select
                value={draft.status}
                onChange={(e) => change({ status: e.target.value })}
              >
                <option value="unreviewed">Chưa review</option>
                <option value="reviewing">Đang review</option>
                <option value="reviewed">Đã review</option>
              </select>
              <h3>KẾT LUẬN</h3>
              <select
                value={draft.verdict}
                onChange={(e) => change({ verdict: e.target.value })}
              >
                {verdicts.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
              <h3>NGUYÊN NHÂN</h3>
              {tags.map((t) => (
                <label key={t}>
                  <input
                    type="checkbox"
                    checked={draft.tags.includes(t)}
                    onChange={(e) =>
                      change({
                        tags: e.target.checked
                          ? [...draft.tags, t]
                          : draft.tags.filter((x) => x !== t),
                      })
                    }
                  />
                  {t}
                </label>
              ))}
              <h3>COMMENT</h3>
              <textarea
                id="comment"
                value={draft.comment}
                onChange={(e) => change({ comment: e.target.value })}
                placeholder="Sai ở bước nào? Bằng chứng và hướng xử lý…"
              />
              <button
                className="primary"
                disabled={saving || !sample}
                onClick={() => save()}
              >
                {saving ? "Đang lưu…" : "Lưu review"}
              </button>
              <small role="status">
                {dirty ? "● Chưa lưu · " : ""}
                {notice}
              </small>
              <small>
                Review được lưu SQLite. Chọn “Đã review” khi hoàn tất.
              </small>
            </fieldset>
          </aside>
        </div>
      )}
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
