"""Read-only synthesis of the 97 authored investigation buckets."""
import collections
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path('review_data')
OUT = ROOT / 'mechanism_synthesis_20261103'
OUT.mkdir(exist_ok=True)
groups = json.loads((ROOT / 'group_causes.json').read_text(encoding='utf-8'))['groups']
p01 = json.loads((ROOT / 'p01_investigation_20261103/prepared.json').read_text(encoding='utf-8'))
groups = dict(groups, P01={'names': {'pipeline': 'Nghi pipeline dừng sớm', 'model': 'Nghi model, có thể kèm pipeline', 'insufficient': 'Chưa đủ bằng chứng', 'not_p01': 'Không thuộc P01'}, 'samples': {r['sample_id']: r['conclusion'] for r in p01}})

# Explicit human-authored crosswalk; no keyword inference or reassignment of reviews.
specs = [
 ('R01','Pipeline kết thúc khi còn tác vụ chưa xử lý','co_che_tinh','P0','P01:pipeline', 'Replay 0052, 0672, 0830; so sánh barrier hiện tại với tiếp tục có giới hạn. Kiểm tra hỏi thiếu thông tin, write lặp và done=false; không bỏ barrier vô điều kiện.'),
 ('R02','Chọn sai nghiệp vụ, nguồn hoặc hiểu sai tác dụng tool','gia_thuyet','P1','M06:bill_transfer,autopay_pay,reminder_alarm,reminder_medication,quote_booking,beneficiary_contact,restore_cancelled,meeting_source,points_vouchers,checkin_search,balance_expense,recipe_menu,call_sms M03:wrong_workflow M02:wrong_api M14:wrong_quantity M05:wrong_measure', 'Đối chiếu intent với tiền/hậu điều kiện của tool; phân biệt read, cấu hình và thực thi. Replay 0088, 0817, 1141; riêng 0111 cần tách ảnh hưởng pipeline.'),
 ('R03','Tự chọn ứng viên hoặc điền dữ liệu thiếu căn cứ','gia_thuyet','P1','M02:relation,first,chat,preference,history,placeholder M03:invent_time,skip_lookup,invent_id,example_id,context_mix,invent_evidence,enum_unknown,invent_level', 'Tra cứu nguồn thích hợp trước; lưu nguồn của giá trị; hỏi khi còn thiếu hoặc nhiều ứng viên. Thử 0116, 1292, 1449; kiểm tra cả case đủ dữ liệu để tránh hỏi thừa.'),
 ('R04','Không giữ điều kiện và nhánh hành động','gia_thuyet','P1','M14:price_as_fact,weather_omitted,fallback_unchecked,status_omitted,send_condition,message_omitted M05:branch_leak,partial_payment,false_still_act,reverse_predicate,aggregate_fallback,history_gate', 'Biểu diễn điều kiện, nguồn kiểm tra, nhánh được phép và fallback. Thử 0190, 0423, 097; kiểm tra điều kiện false không tạo write và không suy diễn thanh toán một phần.'),
 ('R05','Mất ý định cuối cùng sau lời sửa hoặc rút yêu cầu','gia_thuyet','P1','M19:revoked_to_plan,cancel_scope,channel_fallback,correction_lost,correction_ignored,unneeded_meta,revoked_grant M03:withdrawn', 'Chốt ý định còn hiệu lực trước tool call, giữ sau read; thiếu kênh mới không phục hồi yêu cầu đã rút. Thử 0957, 1084, 1286; kiểm tra không thực thi và không hỏi tham số cho ý định đã hủy.'),
 ('R06','Quy đổi sai mốc, chuỗi hoặc hướng thời gian','gia_thuyet','P1','M04:weekday,chain,updated_anchor,clock,direction,missing_anchor,explicit,relative', 'Chuẩn hóa anchor/timezone và phép cộng trừ, dùng hàm xác định ngày trước khi write. Thử 0546, 0124, 0381; không dùng kiểm tra format để thay kiểm tra ngữ nghĩa.'),
 ('R07','Truy vấn làm mất bằng chứng hoặc ứng viên','gia_thuyet','P1','M18:since_now,date_window,location_mismatch,null_string,candidate_coverage M02:coverage', 'Phân biệt thiếu ID với chuỗi None; kiểm tra semantics filter, mở rộng truy vấn nếu thiếu bao phủ. Thử 0676, 1105, 1449; không mặc định kết quả rỗng đồng nghĩa không tồn tại.'),
 ('R08','Giải mã sai literal trong lời nói','gia_thuyet','P2','M03:spoken_literal', 'Kiểm tra tách token email và số người nhận với 0681; đối chiếu text/audio nếu có, không tự thêm địa chỉ.'),
 ('R09','Tự thêm giá trị vận hành hoặc metadata mâu thuẫn','gia_thuyet','P1','D03:task_priority,device_setting,label_conflict', 'Phân biệt optional với được phép tự chọn; giữ thông số hiện tại/default khi không có yêu cầu. Thử 0643, 1123, 0103; label mâu thuẫn là lỗi hiển thị riêng với state canonical.'),
 ('V01','Khác biệt hợp lệ hoặc tương đương trong phạm vi bằng chứng','doi_chung','P3','D02:scope,context,default,broad D04:repeat,priority,timestamp,calendar_end,route_mode,email_default,date_scope M18:recovered', 'Giữ làm regression và diễn giải scorer. recovered chỉ chứng minh truy vấn đã phục hồi, không chứng minh toàn sample đúng. date_scope không phải runtime default.'),
 ('Q01','Tương đương phụ thuộc state hoặc cần chốt chính sách','chinh_sach','P2','D02:coverage,window,unjustified D04:robot_mode M02:tie_policy D03:alarm_label,transfer_note,delivery_address,guest_label,calendar_location', 'Chốt riêng phạm vi lịch sử, hòa giá, địa chỉ và optional text. Đọc canonical/scorer; không bỏ mọi optional field. Thử 1712, 0298, 0267 và state robot khác.'),
 ('C01','Contract tham số không được runtime thực hiện','co_che_tinh','P2','D02:ignored', 'Đối chiếu tài liệu/schema với order_history.limit; quyết định triển khai limit hay sửa contract. Kiểm tra 1499, 1547 với dữ liệu dài hơn limit.'),
 ('X01','Lỗi đầu tiên do model nhưng chưa tách hết pipeline','tong_hop','P2','P01:model', 'Đây là bucket hỗn hợp; không thêm một root cause mới. Dùng kết luận chuyên biệt của các nhóm M và replay ghép cặp trước khi quy trách nhiệm pipeline.'),
 ('X02','Trạng thái thiếu bằng chứng, loại phạm vi hoặc write chưa xảy ra','trang_thai','P3','P01:insufficient,not_p01 D03:failed_write', '1178 cần giữ kết luận reviewer; 1750 không thuộc P01; 1564 không suy note đã lưu từ raw write thất bại. Không tính các mục này là nguyên nhân độc lập.'),
]

protected = [ROOT/'snapshot.json',ROOT/'error_analysis.json',ROOT/'group_causes.json',ROOT/'reviews.sqlite']
def hashes(): return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before = hashes()
conn = sqlite3.connect(f'file:{(ROOT/"reviews.sqlite").resolve().as_posix()}?mode=ro', uri=True)
evidence = {}
for sid, key, payload in conn.execute('select sample, analysis_key, payload from investigations'):
    if key == json.loads((ROOT/'group_causes.json').read_text(encoding='utf-8'))['analysis_key']:
        evidence[sid] = json.loads(payload)
conn.close()
rows=[]; seen=set()
for code,title,kind,priority,mapping,action in specs:
    buckets=[]; samples=set()
    for token in mapping.split():
        group, keys=token.split(':')
        for key in keys.split(','):
            assert (group,key) not in seen
            seen.add((group,key))
            ids=sorted(s for s,k in groups[group]['samples'].items() if k==key)
            assert ids, (group,key)
            samples.update(ids)
            buckets.append({'group':group,'key':key,'name':groups[group]['names'][key],'sample_ids':ids})
    rows.append(dict(id=code,title=title,kind=kind,priority=priority,buckets=buckets,sample_ids=sorted(samples),next_action=action))
expected={(g,k) for g,v in groups.items() for k in v['names']}
assert seen==expected, (expected-seen,seen-expected)
assert len(seen)==97
all_ids=sorted({s for r in rows for s in r['sample_ids']})
assert set(all_ids)<=set(evidence)
sample_map={s:[r['id'] for r in rows if s in r['sample_ids']] for s in all_ids}
(OUT/'mechanisms.json').write_text(json.dumps({'scope':'12 investigated groups only; not all 300 samples','buckets':97,'mechanisms':rows,'sample_map':sample_map},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'evidence.json').write_text(json.dumps({s:evidence[s] for s in all_ids},ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Tổng hợp cơ chế từ 12 nhóm đã điều tra · 03/11/2026','',f'97 bucket được ánh xạ đầy đủ vào {len(rows)} cụm tổng hợp; {len(all_ids)} sample duy nhất. Đây không phải {len(rows)} root cause đã xác nhận. Phạm vi chỉ gồm 12 nhóm đã điều tra; chưa phân tích thêm 34 nhóm còn lại. Không replay, không sửa pipeline, không thay review/comment/phân loại/UI.','', '9 cụm R là cơ chế lỗi cần kiểm chứng; C01 là lệch contract/runtime có bằng chứng code. V01 là đối chứng, Q01 là chính sách, X01 là bucket hỗn hợp, X02 là trạng thái kết luận. Một sample có thể thuộc nhiều cụm; số sample là mức liên quan, không phải số case sẽ sửa được. P0/P1 là ưu tiên xác minh, không khẳng định tỷ lệ cải thiện.','', 'Nguồn: group_causes.json, P01/prepared.json và investigations hiện hành trong SQLite. evidence.json giữ nguyên bằng chứng/replay/revision hiện tại để đọc từng sample; mechanisms.json chứa crosswalk toàn bộ bucket và sample_map. Báo cáo cũ theo nhóm vẫn là nguồn điều tra chi tiết.','', '| Cụm | Cơ chế / loại kết luận | Bucket | Sample duy nhất | Ưu tiên |','|---|---|---:|---:|---|']
for r in rows: lines.append(f'| {r["id"]} | {r["title"]} | {len(r["buckets"])} | {len(r["sample_ids"])} | {r["priority"]} |')
lines+=['','## Kế hoạch xác minh','', '1. R01: dùng ba case 0052, 0672, 0830 đã chọn, khi có server. Giữ nguyên input/model/seed nếu hỗ trợ; chỉ đổi stop policy trong simulator.','2. R04 và R05: kiểm tra hành động không được phép trước; thêm control nhánh true/false và ý định có/không bị rút.','3. R02/R03/R06/R07: kiểm tra riêng công cụ, grounding, thời gian và bao phủ truy vấn; không thay nhiều cơ chế trong cùng phép thử.','4. Q01/V01: thống nhất cách chấm trước khi đổi scorer; dùng các case đúng làm regression.','5. Sau replay mới chọn fix cụ thể và chạy tập lỗi + control. Theo dõi tool/state, hành động thừa, hỏi thừa, số lượt và latency <30s. Không suy ra hiệu quả từ reasoning hoặc số lượng bucket.','']
for r in rows:
    lines += [f'## {r["id"]} · {r["title"]}','',f'Loại: `{r["kind"]}`. Ưu tiên: {r["priority"]}. {r["next_action"]}','', '| Mục nguồn | Nhận định nguồn | Sample |','|---|---|---|']
    for b in r['buckets']: lines.append(f'| {b["group"]}:{b["key"]} | {b["name"]} | '+', '.join(b['sample_ids'])+' |')
    lines.append('')
lines+=['## Chỉ mục bằng chứng theo sample','','Bằng chứng đầy đủ của từng sample nằm trong [evidence.json](evidence.json), gồm kết luận và các block điều tra đã lưu; không coi cụm tổng hợp thay thế phán quyết reviewer.','']
for sid, codes in sample_map.items(): lines.append(f'- `{sid}`: '+', '.join(codes))
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
after=hashes()
assert before==after, 'Source data changed during synthesis; inspect concurrency before using output'
verification={'source_hashes_unchanged':True,'source_hashes':after,'groups':len(groups),'source_buckets':len(seen),'synthesis_clusters':len(rows),'unique_samples':len(all_ids),'evidence_coverage':len(all_ids),'counts':[{'id':r['id'],'buckets':len(r['buckets']),'samples':len(r['sample_ids'])} for r in rows],'replay':False,'ui_changed':False}
(OUT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False,indent=2))
