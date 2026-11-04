import os,json,logging,copy
from pathlib import Path
from uuid import uuid4,uuid5,UUID
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from dotenv import load_dotenv
from langsmith import Client
load_dotenv('.env');logging.disable(logging.CRITICAL)
c=Client(api_url=os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com'),timeout_ms=60000,auto_batch_tracing=False)
s=json.loads(Path('logs/merge_experiments_snapshot.json').read_text(encoding='utf-8'))
roots=s['selected'];runs=s['runs'];oldids={r['id'] for r in runs}
assert len(oldids)==len(runs)
assert {r['id'] for r in roots}=={r['id'] for r in runs if not r['parent_run_id']}
assert all(not r['parent_run_id'] or r['parent_run_id'] in oldids for r in runs)
assert len({r['reference_example_id'] for r in roots})==len(roots)==300
assert not any(r.get('error') for r in roots)
assert not any(r.get('attachments') for r in runs),'Attachments require explicit copy'
mp=Path('logs/merged_experiment_manifest.json')
if mp.exists():m=json.loads(mp.read_text(encoding='utf-8'))
else:
 m={'namespace':str(uuid4()),'name':'lifemate-merged-retry-fixed-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'),'sources':s['sources'],'dataset_id':s['dataset_id'],'excluded':s['excluded'],'source_counts':dict(Counter(r['session_id'] for r in roots))}
 mp.write_text(json.dumps(m,indent=2),encoding='utf-8')
ns=UUID(m['namespace']);ids={rid:str(uuid5(ns,rid)) for rid in oldids}
meta={'composite_experiment':True,'source_experiment_ids':s['sources'],'selection_policy':'Prefer rerun; exclude max retries errors; fallback to original','source_counts':m['source_counts'],'excluded_samples':s['excluded']}
if not m.get('project_id'):
 p=c.create_project(m['name'],reference_dataset_id=s['dataset_id'],description='Composite of original successful rows and fixed reruns. Original timings and feedback retained; mixed code versions, not a single benchmark execution.',metadata=meta)
 m['project_id']=str(p.id);mp.write_text(json.dumps(m,indent=2),encoding='utf-8')
print('project',m['project_id'],m['name'],flush=True)
payload=[]
for r in sorted(runs,key=lambda r:r['dotted_order']):
 d={k:copy.deepcopy(r[k]) for k in ['name','run_type','inputs','outputs','error','start_time','end_time','serialized','events','tags','extra','reference_example_id'] if r.get(k) is not None}
 d.update(id=ids[r['id']],trace_id=ids[r['trace_id']],session_name=m['name'],session_id=m['project_id'],dotted_order='.'.join(seg[:-36]+ids[seg[-36:]] for seg in r['dotted_order'].split('.')))
 if r['parent_run_id']:d['parent_run_id']=ids[r['parent_run_id']]
 d.setdefault('extra',{}).setdefault('metadata',{}).update(source_run_id=r['id'],source_experiment_id=r['session_id'],composite_experiment=True)
 payload.append(d)
for i in range(0,len(payload),100):
 c.batch_ingest_runs(create=payload[i:i+100],pre_sampled=True)
 print('copied trace nodes',min(i+100,len(payload)),'/',len(payload),flush=True)
def feedback(f):
 kw={k:f[k] for k in ['score','value','correction','comment','extra'] if f.get(k) is not None}
 info=copy.deepcopy((f.get('feedback_source') or {}).get('metadata') or {})
 info.update(source_feedback_id=f['id'],source_run_id=f['run_id'],copied_from_source_experiment=True)
 return c.create_feedback(run_id=ids[f['run_id']],key=f['key'],feedback_id=uuid5(ns,'feedback:'+f['id']),source_info=info,**kw)
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(feedback,s['feedback']))
print('copied feedback',len(s['feedback']),flush=True)
c.update_project(m['project_id'],metadata=meta,end_time=datetime.now(timezone.utc))
m.update(expected_roots=len(roots),expected_nodes=len(runs),expected_feedback=len(s['feedback']))
mp.write_text(json.dumps(m,indent=2),encoding='utf-8')
print('upload complete',flush=True)
