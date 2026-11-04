import os,json,logging
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
from langsmith import Client
load_dotenv('.env');logging.disable(logging.CRITICAL)
c=Client(api_url=os.getenv('LANGSMITH_ENDPOINT','https://api.smith.langchain.com'),timeout_ms=60000)
m=json.loads(Path('logs/merged_experiment_manifest.json').read_text(encoding='utf-8'))
s=json.loads(Path('logs/merge_experiments_snapshot.json').read_text(encoding='utf-8'))
rs=list(c.list_runs(project_id=m['project_id']))
roots=[r for r in rs if not r.parent_run_id];expected={r['id']:r for r in s['selected']}
assert len(rs)==m['expected_nodes'],(len(rs),m['expected_nodes'])
assert len(roots)==m['expected_roots']==len({r.reference_example_id for r in roots})
assert not any(r.error for r in roots)
assert len({r.inputs['sample_id'] for r in roots})==300
scores={}
for r in roots:
 src=expected[r.extra['metadata']['source_run_id']]
 assert r.inputs==src['inputs'] and r.outputs==src['outputs']
 assert str(r.reference_example_id)==src['reference_example_id']
 assert r.start_time.isoformat()==src['start_time'] or r.start_time.isoformat().replace('+00:00','Z')==src['start_time']
 for k,v in src['feedback_stats'].items():
  assert r.feedback_stats[k]['n']==v['n'] and r.feedback_stats[k]['avg']==v['avg'],(r.id,k,r.feedback_stats,src['feedback_stats'])
  scores.setdefault(k,[]).append(r.feedback_stats[k]['avg'])
ids={str(r.id) for r in rs}
assert all(not r.parent_run_id or str(r.parent_run_id) in ids for r in rs)
counts=Counter(r.extra['metadata']['source_experiment_id'] for r in roots)
assert dict(counts)==m['source_counts']
report={**m,'verified_roots':len(roots),'verified_nodes':len(rs),'retry_errors':0,'duplicate_samples':0,'metrics':{k:sum(v)/len(v) for k,v in scores.items()},'verified_source_counts':dict(counts)}
Path('logs/merged_experiment_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
