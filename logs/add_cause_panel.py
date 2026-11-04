from pathlib import Path
p=Path('review-ui/src/ErrorAnalysis.jsx')
s=p.read_text(encoding='utf-8')
old='</div><div className="analysis-list">{visible.map(r =>'
new='''</div>
        <div className="analysis-panelhead">
          <h3>Nhóm nguyên nhân / giả thuyết</h3>
          <p>Dựa trên kết luận điều tra đã lưu, chưa mặc định được xác nhận bằng replay. Có {searched.length} sample liên quan trong bộ lọc, gồm cả nhóm chính và nhóm phụ.</p>
          {cause === null ? <div className="cause-list">
            {causeCounts.map(([id, name, count]) => <button key={id} data-cause={id} onClick={() => { setCause(id); setSampleId(""); }}><span>{name}</span><b>{count}</b></button>)}
            <button data-cause="all" onClick={() => { setCause(""); setSampleId(""); }}><span>Xem tất cả sample liên quan</span><b>{searched.length}</b></button>
          </div> : <>
            <button onClick={() => setCause(null)}>Quay lại nhóm nguyên nhân</button>
            <p><strong>{cause === "" ? "Tất cả nguyên nhân" : causeNames[cause]}</strong> · {visible.length} sample</p>
          </>}
        </div>
        <div className="analysis-list">{visible.map(r =>'''
assert s.count(old)==1
s=s.replace(old,new)
s=s.replace('Không có sample phù hợp bộ lọc.</p> : <>','{cause === null ? "Chọn nhóm nguyên nhân / giả thuyết để xem các sample." : "Không có sample phù hợp bộ lọc."}</p> : <>')
p.write_text(s,encoding='utf-8')
