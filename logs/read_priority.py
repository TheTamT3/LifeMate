import json,sys
x=json.load(open('logs/priority-six-source.json',encoding='utf-8'))
group=sys.argv[1]; start=int(sys.argv[2]) if len(sys.argv)>2 else 0; end=int(sys.argv[3]) if len(sys.argv)>3 else 100
def clip(v,n):
 s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)
 return s if len(s)<=n else s[:n//2]+' ... [middle omitted; inspect separately] ... '+s[-n//2:]
rows=[r for r in x['rows'] if group in [r['primary_group']]+r['secondary_groups'] or group==r['sample_id']]
for r in rows[start:end]:
 print('\n###',r['sample_id'],r['question'])
 print('COMMENT',x['reviews'].get(r['sample_id'],r['existing_review']).get('comment'))
 print('CONTEXT',clip({k:v for k,v in r['context'].items() if k!='installed_apps'},1500))
 print('SUMMARY',r['evidence_summary'],'\nLIMIT',r['cause_and_limits'])
 for t in r['executed_tools']:print('EXEC',t['name'],clip(t['inputs'],1200),'OUT',clip(t['outputs'],1600))
 print('REF',clip(r['reference_calls'],4000))
 for n in r['llm_evidence']:
  print('LLM',n['id'])
  for p in n['parts']:print(p.get('part_kind'),p.get('tool_name',''),clip(p.get('args',p.get('content','')),2200))
 if '--history' in sys.argv:
  for h in r['history']:print('HISTORY',clip(h,5000))
