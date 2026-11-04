import os,json,logging
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
load_dotenv('.env');logging.disable(logging.CRITICAL)
c=Client(api_url=os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com'),timeout_ms=30000)
out={}
for pid in ['018769bd-b6ea-465f-8a0d-3fd79d38a6b9','99bc0d7b-580d-4e24-889c-582c0662661b']:
 p=c.read_project(project_id=pid);rs=list(c.list_runs(project_id=pid,is_root=True))
 out[pid]={'project':json.loads(p.json()),'runs':[json.loads(r.json()) for r in rs]}
 print(json.dumps({'id':pid,'name':p.name,'dataset':str(p.reference_dataset_id),'roots':len(rs),'unfinished':sum(r.end_time is None for r in rs),'retry_errors':sum(bool(r.error and 'exceeded max retries count of 1' in r.error) for r in rs),'other_errors':sum(bool(r.error and 'exceeded max retries count of 1' not in r.error) for r in rs),'sample_run':{'inputs':rs[0].inputs,'feedback_stats':rs[0].feedback_stats}},default=str))
Path('logs/merge_experiments_sources.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

