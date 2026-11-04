"""Read-only adjudication export; never updates reviews or the active analysis."""
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'review_data'
OUT = BASE / 'feedback_adjudication_20261103'
OUT.mkdir(exist_ok=True)
analysis_bytes = (BASE / 'error_analysis.json').read_bytes()
snapshot_digest = hashlib.sha256((BASE / 'snapshot.json').read_bytes()).hexdigest()
analysis = json.loads(analysis_bytes)
key = hashlib.sha256(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def state():
    with sqlite3.connect(f'file:{(BASE / "reviews.sqlite").as_posix()}?mode=ro', uri=True) as db:
        return {
            'reviews': dict(db.execute('SELECT sample,payload FROM reviews')),
            'feedback': {(s,k): p for s,k,p in db.execute('SELECT sample,analysis_key,payload FROM analysis_feedback')},
        }

before = state()
feedback = {s: json.loads(p) for (s,k),p in before['feedback'].items() if k == key}
records = {r['sample_id']:r for r in analysis['records']}
ids = analysis['priority_review_ids']
rows = []
for sid in ids:
    record = records[sid]
    saved = feedback.get(sid)
    status = (saved or {}).get('status', 'unreviewed')
    if status == 'agree':
        resolution = 'Người review xác nhận nhận định phân nhóm hiện tại. Giữ kết luận; không tự thay verdict/comment review.'
        decision = 'confirmed'
    elif status == 'disagree':
        resolution = ('Theo quy ước người dùng đã xác nhận: Không đồng ý nghĩa là comment cũ đúng. '
                      'Dùng comment review cũ làm kết luận adjudication, bác bỏ nhận định phân nhóm mới cho sample này; '
                      'không yêu cầu ghi chú bổ sung. Bằng chứng trace và nhận định trước vẫn giữ nguyên để truy vết; '
                      'đây là kết luận review, không phải kết quả replay xác minh nguyên nhân runtime.')
        decision = 'retain_original_review'
    else:
        resolution = 'Chưa có đối chiếu hoàn tất được lưu cho bản phân tích hiện tại. Không suy ra đồng ý từ việc đã mở sample.'
        decision = 'pending'
    rows.append(dict(sample_id=sid, primary_group=record['primary_group'], status=status,
                     feedback=saved, decision=decision, resolution=resolution,
                     original_assessment=record['assessment'], evidence_summary=record['evidence_summary'],
                     comparison_with_existing_comment=record['comparison_with_existing_comment'],
                     existing_review=json.loads(before['reviews'][sid])))

counts = dict(Counter(r['status'] for r in rows))
p01 = [r for r in analysis['records'] if r['primary_group']=='P01']
deferred = [r['sample_id'] for r in p01 if feedback.get(r['sample_id'],{}).get('status') == 'disagree']
payload = dict(created_at=datetime.now(timezone.utc).isoformat(), analysis_key=key,
               experiment=analysis['experiment'], counts=counts, records=rows,
               p01_primary_candidates=[r['sample_id'] for r in p01], p01_deferred_due_to_feedback=deferred,
               controlled_replay=False, active_analysis_modified=False, reviews_modified=False)
(OUT/'adjudication.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
names = {'agree':'Đồng ý','disagree':'Không đồng ý','unreviewed':'Chưa lưu','needs_check':'Cần kiểm tra thêm'}
lines = ['# Tổng hợp đối chiếu 13 sample — 03/11/2026', '',
         f'Bản phân tích: `{key}`. Chỉ đọc feedback của đúng phiên bản này.', '',
         f'Đồng ý: {counts.get("agree",0)}; Không đồng ý: {counts.get("disagree",0)}; Chưa lưu: {counts.get("unreviewed",0)}.', '',
         '## Kết luận', '',
         '- 7 nhận định được xác nhận: 0035, 0097, 0178, 0511, 0703, 0812, 0837. Đây là xác nhận phân tích, không phải tự động cập nhật verdict.',
         '- 6 sample giữ comment cũ: 0437, 1178, 1305, 1412, 1510, 1629. Người dùng xác nhận Không đồng ý nghĩa là comment cũ đúng, không cần ghi chú bổ sung.',
         '- Đã có đủ 13 đối chiếu được lưu. Không tự thay verdict/comment hoặc ghi lại feedback.', '',
         '## Từng sample', '', '| Sample | Nhóm đề xuất | Đối chiếu | Ghi chú reviewer |', '|---|---|---|---|']
for r in rows:
    note=(r['feedback'] or {}).get('note','').strip().replace('|','/').replace('\n',' ')
    lines.append(f'| {r["sample_id"]} | {r["primary_group"]} | {names[r["status"]]} | {note or "—"} |')
for r in rows:
    lines += ['', f'### {r["sample_id"]}', '', r['resolution'], '', '**Comment review cũ:**', '', r['existing_review'].get('comment',''), '', '**Bằng chứng đã ghi nhận (giữ để truy vết):** '+r['evidence_summary']]
lines += ['', '## Bước kế tiếp cho P01', '',
          f'Có {len(p01)} sample nhóm chính P01. Đây là ứng viên kiểm chứng, chưa phải {len(p01)} lỗi pipeline đã chứng minh bằng replay.',
          '1178 dùng comment cũ theo kết luận reviewer; không dùng nhận định P01 mới đã bị bác bỏ làm case xác nhận pipeline. Danh sách P01 còn lại cần rà lại và replay có kiểm soát; chưa sửa điều kiện dừng trong bước tổng hợp này.',
          'Ưu tiên kiểm chứng 0672 để quan sát có phát sinh lượt LLM tiếp theo sau tool ghi hay không, rồi đánh giá các thao tác bổ sung. Không replay tác động bên ngoài; dùng môi trường simulator riêng cho từng sample.', '',
          'Không sửa bản phân tích đang chạy: digest thay đổi sẽ làm feedback cũ không còn hiện ở phiên bản mới. Bản tổng hợp này là lớp kết luận bổ sung đã áp dụng quy ước feedback người dùng, tách khỏi dữ liệu phân nhóm gốc.']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
assert state() == before, 'Review or feedback changed during export; re-read before publishing.'
assert (BASE/'error_analysis.json').read_bytes()==analysis_bytes
assert hashlib.sha256((BASE/'snapshot.json').read_bytes()).hexdigest()==snapshot_digest
(OUT/'verification.json').write_text(json.dumps(dict(counts=counts, total=len(rows),
    reviews_unchanged=True, feedback_unchanged=True, active_analysis_unchanged=True,
    snapshot_unchanged=True, analysis_key=key), indent=2), encoding='utf-8')
print(json.dumps(dict(counts=counts,total=len(rows),p01_primary_candidates=len(p01),deferred=deferred,unchanged=True)))
