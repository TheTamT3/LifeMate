import os,json,logging
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
load_dotenv('.env');logging.disable(logging.CRITICAL)
c=Client(api_url=os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com'),timeout_ms=60000)
d=json.loads(Path('logs/merge_experiments_sources.json').read_text(encoding='utf-8'))
base,retry=list(d)
def key(r):return r['reference_example_id']
old={key(r):r for r in d[base]['runs']};new={key(r):r for r in d[retry]['runs']}
assert len(old)==300 and len(new)==70
assert set(new)<=set(old)
selected=[];excluded=[]
for k,r in old.items():
 n=new.get(k)
 assert not n or n['inputs']['sample_id']==r['inputs']['sample_id']
 valid=lambda x: x and not (x.get('error') and 'exceeded max retries count of 1' in x['error'])
 chosen=n if valid(n) else r if valid(r) else None
 if chosen:selected.append(chosen)
 else:excluded.append(r['inputs']['sample_id'])
print('selected',len(selected),'excluded',len(excluded),flush=True)
keep={r['id'] for r in selected};all_runs=[]
for pid in d:
 rs=list(c.list_runs(project_id=pid))
 rs=[json.loads(r.json()) for r in rs if str(r.trace_id) in keep]
 all_runs.extend(rs)
 print('source',pid,'selected trace nodes',len(rs),flush=True)
feedback=[]
for i in range(0,len(selected),50):
 feedback.extend(json.loads(f.json()) for f in c.list_feedback(run_ids=[r['id'] for r in selected[i:i+50]]))
payload={'selected':selected,'excluded':excluded,'runs':all_runs,'feedback':feedback,'sources':list(d),'dataset_id':d[base]['project']['reference_dataset_id']}
Path('logs/merge_experiments_snapshot.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('snapshot saved',len(all_runs),'nodes',len(feedback),'feedback',flush=True)
