"""Append manually investigated findings; never invokes an LLM or simulator."""
import argparse
import hashlib
import json
import sqlite3
import urllib.request
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

BASE='http://127.0.0.1:8765'
OUT=Path('review_data/priority_six_investigation_20261103')
GROUPS=['M03','M14','M05','M19','M06','M18','D03']
SPEC=json.loads(Path('logs/priority-six-findings.json').read_text(encoding='utf-8'))

def get(path):
 with urllib.request.urlopen(BASE+path,timeout=30) as response:return json.load(response)

def dump(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def matches(row,group):return group in [row['primary_group']]+row['secondary_groups']

def marker(group):return '['+group+' · Điều tra'

def excerpts(row):
 result=[]
 for node in row['llm_evidence']:
  parts=[]
  for part in node['parts']:
   value=deepcopy(part)
   content=value.get('content','')
   if len(content)>4500:
    value['content']=content[:2500]+'\n[Trích đầu/cuối; reasoning đầy đủ trong source.json]\n'+content[-2000:]
   parts.append(value)
  result.append({'id':node['id'],'error':node['error'],'parts':parts})
 return result

def main(save=False):
 OUT.mkdir(exist_ok=True)
 data=get('/api/analysis'); reviews=get('/api/reviews'); before=get('/api/export')
 rows=[r for r in data['records'] if any(matches(r,g) for g in GROUPS)]
 assert len(rows)==84
 key=data['feedback_key']
 paths=[Path('review_data/error_analysis.json'),Path('review_data/snapshot.json'),Path('review_data/group_causes.json')]
 original={str(p):p.read_bytes() for p in paths}
 taxonomy=json.loads(original[str(paths[2])])
 assert taxonomy['analysis_key']==key
 assert not any(g in taxonomy['groups'] for g in GROUPS),'Already published; inspect saved journal instead of overwriting.'
 checks={}
 for group in GROUPS:
  subset=[r for r in rows if matches(r,group)]
  assert {r['sample_id'][6:] for r in subset}==set(SPEC[group]['findings']),group
  assert set(v[0] for v in SPEC[group]['findings'].values())==set(SPEC[group]['names']),group
  schemas={r['sample_id']:[t['name'] for t in r['llm_evidence'][0]['request_parameters']['function_tools']] for r in subset}
  if group=='M03':assert all('sys_ask_missing_info' in ts for ts in schemas.values())
  counts=Counter(v[0] for v in SPEC[group]['findings'].values())
  checks[group]={'samples':len(subset),'primary':sum(r['primary_group']==group for r in subset),'causes':dict(counts),'cause_groups':len(counts)}
  taxonomy['groups'][group]={'names':SPEC[group]['names'],'samples':{'train_'+s:v[0] for s,v in SPEC[group]['findings'].items()}}
 dump(OUT/'taxonomy_prepared.json',taxonomy)
 prepared=[]
 for row in rows:
  sid=row['sample_id']; old=data['investigations'].get(sid,{})
  groups=[g for g in GROUPS if matches(row,g)]
  review=reviews.get(sid,row['existing_review'])
  blocks=[]
  for group in groups:
   assert marker(group) not in old.get('evidence',''),sid
   cause,finding=SPEC[group]['findings'][sid[6:]]
   blocks.append('\n\n'.join([
    '['+group+' · Điều tra từ trace/history/schema/runtime, chưa replay]',
    'Nhóm nguyên nhân '+group+': '+SPEC[group]['names'][cause],
    'Kết luận riêng sample và hướng xử lý: '+finding,
    'Cơ chế và hướng xử lý cấp nhóm: '+SPEC[group]['common']]))
  provenance='\n\n'.join([
   '[Nguồn đối chiếu chung cho đợt sáu mục ưu tiên · 2026-11-03]',
   'Câu hỏi: '+row['question'],
   'Comment hiện tại đã đối chiếu, giữ nguyên: '+review.get('comment',''),
   'Context: '+json.dumps({k:v for k,v in row['context'].items() if k!='installed_apps'},ensure_ascii=False),
   'History: '+json.dumps(row['history'],ensure_ascii=False),
   'Reasoning/raw call (node ID; trích đầu/cuối nếu lặp quá dài): '+json.dumps(excerpts(row),ensure_ascii=False),
   'Execution: '+json.dumps(row['executed_tools'],ensure_ascii=False),
   'Reference: '+json.dumps({'calls':row['reference_calls'],'results':row['reference_results']},ensure_ascii=False),
   'Trace '+row['root_id']+'; revision '+str(row['trace_revision'])+'. Nguồn đầy đủ: review_data/priority_six_investigation_20261103/source.json, sample_id='+sid,
   'Giới hạn: phân tích trace đã lưu và code hiện tại; chưa replay LLM/simulator sample, chưa nghe audio; không sửa verdict/comment, feedback, gold hoặc phân nhóm gốc. Những hướng fix là đề xuất, chưa được xác nhận chạy lại. Nhận định theo từng nhóm không xóa lỗi độc lập hoặc kết luận điều tra cũ.'])
  payload={'analysis_key':key,'conclusion':old.get('conclusion') or ('insufficient' if groups==['D03'] else 'model'),
   'evidence':old.get('evidence','')+('\n\n' if old else '')+'\n\n'.join(blocks+[provenance]),
   'replay':old.get('replay','not_run'),
   'replay_notes':old.get('replay_notes','')+('\n\n' if old else '')+'Đợt sáu mục ưu tiên ('+', '.join(groups)+'): chưa replay; không đánh dấu xác nhận hướng fix.',
   'revision':old.get('revision',0)}
  assert len(payload['evidence'])<=100000,(sid,len(payload['evidence']))
  prepared.append({'sample_id':sid,'groups':groups,'prior_investigation':old,'payload':payload})
 dump(OUT/'prepared.json',prepared)
 dump(OUT/'source.json',{'analysis_key':key,'rows':rows,'reviews':{r['sample_id']:reviews.get(r['sample_id'],r['existing_review']) for r in rows}})
 dump(OUT/'findings.json',SPEC)
 dump(OUT/'preflight.json',{'groups':checks,'unique_samples':len(rows),'group_memberships':sum(c['samples'] for c in checks.values()),'max_evidence_characters':max(len(p['payload']['evidence']) for p in prepared)})
 lines=['# Điều tra sáu mục ưu tiên · 2026-11-03','',
  'Phạm vi: M03; M14+M05; M19; M06; M18; D03. 84 sample khác nhau, 103 lượt liên quan nhóm. Đây là điều tra tĩnh, chưa replay/chưa sửa pipeline. Đọc comment hiện tại, history, reasoning/raw call, execution, reference và code/schema liên quan. Nguồn đầy đủ trong source.json; nhận định thủ công trong findings.json.','',
  '## Các nhóm nguyên nhân','', '| Nhóm | Liên quan | Chính | Nhóm nguyên nhân |','|---|---:|---:|---:|']
 for g,c in checks.items():lines.append(f"| {g} | {c['samples']} | {c['primary']} | {c['cause_groups']} |")
 for group in GROUPS:
  lines+=['','## '+group,'',SPEC[group]['common'],'']
  for cause,count in sorted(checks[group]['causes'].items(),key=lambda v:(-v[1],v[0])):
   ids=[sid for sid,c in taxonomy['groups'][group]['samples'].items() if c==cause]
   lines+=['- '+SPEC[group]['names'][cause]+f': {count} — '+', '.join(ids)+'.']
  for sid,(cause,finding) in SPEC[group]['findings'].items():
   r=next(r for r in rows if r['sample_id']=='train_'+sid)
   lines+=['','### train_'+sid,'','**Nguyên nhân:** '+SPEC[group]['names'][cause],'',finding,'',
    '**Comment gốc được giữ nguyên:** '+reviews.get(r['sample_id'],r['existing_review']).get('comment',''),'',
    '**Nguồn:** root '+r['root_id']+'; LLM nodes '+', '.join(n['id'] for n in r['llm_evidence'])+'.']
 (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
 if not save:
  print(json.dumps({'prepared':len(prepared),'groups':checks,'max_evidence':max(len(p['payload']['evidence']) for p in prepared)},ensure_ascii=False));return
 assert not (OUT/'saved.json').exists(),'Saved journal exists; do not repeat writes.'
 dump(OUT/'export_before.json',before)
 (OUT/'group_causes_before.json').write_bytes(original[str(paths[2])])
 with sqlite3.connect('review_data/reviews.sqlite') as src,sqlite3.connect(OUT/'before.sqlite') as dst:src.backup(dst)
 # Fail before mutation if a reviewer edited data during preparation.
 fresh=get('/api/analysis')
 assert fresh['investigations']==data['investigations'] and get('/api/reviews')==reviews
 assert get('/api/export')['analysis_feedback']==before['analysis_feedback']
 saved=[]
 for p in prepared:
  request=urllib.request.Request(BASE+'/api/investigation/'+p['sample_id'],data=json.dumps(p['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Origin':BASE},method='PUT')
  with urllib.request.urlopen(request,timeout=30) as response:saved.append({'sample_id':p['sample_id'],**json.load(response)})
  dump(OUT/'saved.json',saved)
 assert paths[2].read_bytes()==original[str(paths[2])]
 tmp=paths[2].with_suffix('.tmp');dump(tmp,taxonomy);tmp.replace(paths[2])
 after=get('/api/analysis');exported=get('/api/export')
 assert get('/api/reviews')==reviews
 assert exported['analysis_feedback']==before['analysis_feedback']
 assert after['feedback_key']==key
 for p in paths[:2]:assert p.read_bytes()==original[str(p)]
 for g,t in data['group_causes'].items():assert after['group_causes'][g]==t
 ids={p['sample_id'] for p in prepared}
 for sid,old in data['investigations'].items():
  if sid not in ids:assert after['investigations'][sid]==old
 for p in prepared:
  actual=after['investigations'][p['sample_id']]
  for field in ['conclusion','evidence','replay','replay_notes']:assert actual[field]==p['payload'][field]
  assert actual['revision']==p['payload']['revision']+1
  if p['prior_investigation']:assert actual['evidence'].startswith(p['prior_investigation']['evidence']+'\n\n')
 for g in GROUPS:assert after['group_causes'][g]==taxonomy['groups'][g]
 check={'saved':len(saved),'groups':checks,'unique_samples':len(rows),'memberships':sum(c['samples'] for c in checks.values()),
  'reviews_unchanged':True,'feedback_unchanged':True,'prior_investigations_preserved':True,'prior_taxonomies_unchanged':True,
  'source_analysis_unchanged':True,'snapshot_unchanged':True,'replay_run':False,'pipeline_changed':False,
  'source_sha256':{str(p):hashlib.sha256(original[str(p)]).hexdigest() for p in paths[:2]},'verified_at':datetime.now(timezone.utc).isoformat()}
 dump(OUT/'verification.json',check)
 print(json.dumps(check,ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--save',action='store_true');args=parser.parse_args();main(args.save)
