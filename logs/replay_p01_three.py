"""Isolated P01 experiment: archived model prefix, then live continuation.

Does not modify repository pipeline code, UI, reviews or LangSmith.
"""
import argparse
import asyncio
import dataclasses
import inspect
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
IDS=('train_0672','train_0830','train_0052')

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base-url',default='http://127.0.0.1:8000/v1')
    p.add_argument('--model-name',default='qwen3-4b')
    p.add_argument('--root',type=Path,default=ROOT/'train+public_test/train+public_test')
    p.add_argument('--out',type=Path,default=ROOT/'logs/p01_three_replay')
    p.add_argument('--live',action='store_true')
    args=p.parse_args(); args.out.mkdir(exist_ok=True,parents=True)
    snapshot=json.loads((ROOT/'review_data/snapshot.json').read_text(encoding='utf-8'))
    analysis=json.loads((ROOT/'review_data/error_analysis.json').read_text(encoding='utf-8'))
    samples={s['id']:s for s in snapshot['samples'] if s['id'] in IDS}
    records={r['sample_id']:r for r in analysis['records'] if r['sample_id'] in IDS}
    sys.path.insert(0,str(args.root/'train'))
    from zaic_tools import ToolEnv
    # Re-execute only archived successful tool calls on fresh in-memory sessions.
    for sid in IDS:
        env=ToolEnv('train',sid,root=str(args.root))
        r=records[sid]
        for tool in r['executed_tools']:
            result=env.call(tool['inputs']['name'],tool['inputs']['arguments'])
            if result!=tool['outputs']:
                raise RuntimeError('Simulator differs from archived execution: '+sid+' '+tool['name'])
        ref=ToolEnv('train',sid,root=str(args.root))
        for call in r['reference_calls']: ref.call(call['name'],call['arguments'])
        dump(args.out/(sid+'_archived.json'),{'id':sid,'mode':'archived_tools_only','tool_calls':env.get_tool_calls(),
            'state_hash':env.get_state_hash(),'reference_state_hash':ref.get_state_hash(),
            'prefix_results_match_archive':True,'state_matches_reference':env.get_state_hash()==ref.get_state_hash(),
            'llm_called':False,'reference_calls':r['reference_calls']})
        print(sid,'archived simulator outputs match; missing next action; live replay not yet run',flush=True)
    if not args.live: return
    # Disable any inherited tracing before loading model libraries.
    os.environ['LANGSMITH_TRACING']='false'
    os.environ['LANGCHAIN_TRACING_V2']='false'
    import lifemate.pydantic_agent as pa
    from lifemate import runner
    from lifemate.data import allowed_tools,load_catalog
    from lifemate.vllm import create_vllm_model,VLLMConfig
    from pydantic_ai.messages import ModelMessagesTypeAdapter
    from pydantic_ai.models.wrapper import WrapperModel
    from pydantic_ai import UsageLimits
    catalog=load_catalog(args.root/'train/train_tools_catalog.json')
    source=inspect.getsource(pa.run_agent)
    old='any(call["kind"] != "read" for call in new_calls)'
    assert source.count(old)==1
    trial_source=source.replace(old,'any(call["kind"] == "meta" for call in new_calls)')
    ns=dict(pa.__dict__)
    exec(compile(trial_source,'<P01 experimental continuation>','exec'),ns)
    trial=ns['run_agent']
    dump(args.out/'experiment.json',{'change':'non-read barrier becomes meta-only barrier, in memory only',
        'max_requests':8,'timeout_seconds':180,'thinking':True,'seed':0,'base_url':args.base_url,'model':args.model_name,
        'warning':'elapsed excludes archived prefix generation; not a full end-to-end latency benchmark'})
    for sid in IDS:
        recorded=[ModelMessagesTypeAdapter.validate_python([{'kind':'response','parts':n['parts']}])[0] for n in records[sid]['llm_evidence']]
        for mode,run in [('baseline',pa.run_agent),('continue_after_write',trial)]:
            live=create_vllm_model(VLLMConfig(args.base_url,args.model_name,8))
            class PrefixModel(WrapperModel):
                def __init__(self):
                    super().__init__(live); self.index=0; self.responses=[]; self.live_requests=0
                async def request(self,messages,model_settings,model_request_parameters):
                    if self.index<len(recorded):
                        response=recorded[self.index]; self.index+=1
                    else:
                        self.live_requests+=1
                        response=await super().request(messages,model_settings,model_request_parameters)
                    self.responses.append(response)
                    return response
            model=PrefixModel()
            env=ToolEnv('train',sid,root=str(args.root))
            sample=samples[sid]['sample']
            tools=allowed_tools(sample,catalog)
            deps=pa.AgentDependencies(env,{t['name']:t for t in tools},8,0)
            agent=pa.build_agent(model,deps)
            history=runner._to_model_messages(runner._history_records(sample,pa.tool_name_map(tools)))
            started=time.monotonic(); error=None
            async def execute():
                # Reuse run_agent's asynchronous loop under an enclosing deadline.
                # The coroutine entry is redirected locally; repository globals stay unchanged.
                run_ns=dict(run.__globals__)
                run_ns['run_agent_coroutine']=lambda coroutine:coroutine
                import types
                async_run=types.FunctionType(run.__code__,run_ns,run.__name__,run.__defaults__,run.__closure__)
                async_run.__kwdefaults__=run.__kwdefaults__
                return await asyncio.wait_for(async_run(agent,deps,sample['audio_text'],message_history=history,instructions=runner._build_system_prompt(sample)),180)
            try: asyncio.run(execute())
            except Exception as exc:error=repr(exc)
            output={'id':sid,'mode':mode,'elapsed_excluding_archived_generation':time.monotonic()-started,
                'error':error or getattr(deps,'error',None),'live_requests':model.live_requests,
                'calls':env.get_tool_calls(),'tool_results':env.log,'state_hash':env.get_state_hash(),
                'responses':ModelMessagesTypeAdapter.dump_python(model.responses,mode='json'),
                'argument_normalizations':deps.argument_normalizations}
            dump(args.out/(sid+'_'+mode+'.json'),output)
            print(sid,mode,'calls',len(output['calls']),'live',model.live_requests,'error',output['error'],flush=True)

if __name__=='__main__':main()
