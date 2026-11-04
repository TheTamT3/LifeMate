import json, sqlite3, urllib.request
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

BASE = 'http://127.0.0.1:8765'
OUT = Path('review_data/m04_investigation_20261103')
SPEC=json.loads(Path("logs/m04-findings.json").read_text(encoding="utf-8"))
NAMES=SPEC["names"]
FINDINGS=SPEC["findings"]
COMMON=SPEC["common"]

def get(path):
 with urllib.request.urlopen(BASE+path) as r: return json.load(r)

def main():
 OUT.mkdir(exist_ok=True)
 data=get('/api/analysis'); before=get('/api/export'); reviews=get('/api/reviews')
 rows=[r for r in data['records'] if r['primary_group']=='M04' or 'M04' in r['secondary_groups']]
 assert {r['sample_id'] for r in rows} == {'train_'+s for s in FINDINGS}
 paths=[Path('review_data/error_analysis.json'),Path('review_data/snapshot.json'),Path('review_data/group_causes.json')]
 original={str(p):p.read_bytes() for p in paths}
 causes=json.loads(original[str(paths[2])]); assert 'M04' not in causes['groups']
 (OUT/'group_causes_before.json').write_bytes(original[str(paths[2])])
 (OUT/'export_before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
 with sqlite3.connect('review_data/reviews.sqlite') as src,sqlite3.connect(OUT/'before.sqlite') as dst: src.backup(dst)
 prepared=[]
 for r in rows:
  sid=r['sample_id']; cause,finding=FINDINGS[sid.split('_')[1]]; old=data['investigations'].get(sid,{})
  assert '[M04 · Điều tra' not in old.get('evidence','')
  review=reviews.get(sid,r['existing_review'])
  block='\n\n'.join(['[M04 · Điều tra từ trace/history/schema/runtime, chưa replay]','Nhóm nguyên nhân M04: '+NAMES[cause],finding,
   'Câu hỏi: '+r['question'],'Comment hiện tại đã đọc, giữ nguyên: '+review.get('comment',''),
   'Execution và node bằng chứng: '+json.dumps(r['executed_tools'],ensure_ascii=False),
   'Reference: '+json.dumps({'calls':r['reference_calls'],'results':r['reference_results']},ensure_ascii=False),
   'History đối chiếu: '+json.dumps(r['history'],ensure_ascii=False),
   'LLM nodes: '+', '.join(n['id'] for n in r['llm_evidence']),COMMON,
   'Giới hạn: kết luận cơ chế quan sát từ trace và code hiện tại; chưa replay, chưa nghe audio. Không thay review, feedback, gold hoặc phân nhóm gốc. Kết luận M04 không xóa các lỗi độc lập trong sample.'])
  payload={'analysis_key':data['feedback_key'],'conclusion':old.get('conclusion') or ('insufficient' if cause=='tie_policy' else 'model'),
   'evidence':old.get('evidence','')+('\n\n' if old else '')+block,'replay':old.get('replay','not_run'),
   'replay_notes':old.get('replay_notes','')+('\n\n' if old else '')+'M04: chưa replay; hướng fix mới là đề xuất, chưa xác nhận bằng chạy model.', 'revision':old.get('revision',0)}
  assert len(payload['evidence'])<=100000
  prepared.append({'sample_id':sid,'cause_group':cause,'finding':finding,'prior_investigation':old,'block':block,'payload':payload})
 (OUT/'prepared.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),encoding='utf-8')
 saved=[]
 for p in prepared:
  req=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(p['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':BASE},method='PUT')
  with urllib.request.urlopen(req) as response: saved.append({'sample_id':p['sample_id'],**json.load(response)})
  (OUT/'saved.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
 causes['groups']['M04']={'names':NAMES,'samples':{p['sample_id']:p['cause_group'] for p in prepared}}
 tmp=paths[2].with_suffix('.tmp');tmp.write_text(json.dumps(causes,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(paths[2])
 after=get('/api/analysis'); exported=get('/api/export')
 assert get('/api/reviews')==reviews and exported['analysis_feedback']==before['analysis_feedback']
 assert after['feedback_key']==data['feedback_key']
 for p in paths[:2]: assert p.read_bytes()==original[str(p)]
 for group,taxonomy in data['group_causes'].items(): assert after['group_causes'][group]==taxonomy
 ids={p['sample_id'] for p in prepared}
 for sid,old in data['investigations'].items():
  if sid not in ids: assert after['investigations'][sid]==old
 for p in prepared:
  actual=after['investigations'][p['sample_id']]
  for field in ['conclusion','evidence','replay','replay_notes']: assert actual[field]==p['payload'][field]
  if p['prior_investigation']: assert actual['evidence'].startswith(p['prior_investigation']['evidence']+'\n\n')
 counts=Counter(p['cause_group'] for p in prepared)
 check={'saved':len(saved),'primary':sum(r['primary_group']=='M04' for r in rows),'causes':dict(counts),'reviews_unchanged':True,'feedback_unchanged':True,'source_analysis_unchanged':True,'snapshot_unchanged':True,'prior_investigations_preserved':True,'prior_taxonomies_unchanged':True,'replay_run':False,'verified_at':datetime.now(timezone.utc).isoformat()}
 (OUT/'verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
 report=['# Điều tra M04 · 2026-11-03','',f"20 sample liên quan: {check['primary']} nhóm chính, {21-check['primary']} nhóm phụ. Đọc comment hiện tại, history, reasoning, execution và reference. Chưa replay; giữ nguyên review/feedback và điều tra cũ.",'','## Kết luận','',COMMON,'','Phần lớn model nhận ra mơ hồ nhưng vẫn tự chọn. Không cùng một nguyên nhân duy nhất: có sai API trước lựa chọn, lọc thiếu ứng viên, enum thay thông tin thiếu và hai xe đồng hạng cần chính sách riêng. Không coi mọi ID hợp schema là đã có căn cứ nghiệp vụ.','','## Các nhóm nguyên nhân','']
 for cause,count in counts.most_common(): report.append(f'- {NAMES[cause]}: {count}.')
 report+=['','## Từng sample','']
 for p in prepared: report+=['### '+p['sample_id'],'',p['block'],'']
 (OUT/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
 print(json.dumps(check,ensure_ascii=False))

if __name__=='__main__':main()
