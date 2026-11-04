"""Tune on 50 non-validation train queries, confirm on fixed validation audio.
Offline, serial ASR only. Does not change production settings or call an LLM.
"""
from __future__ import annotations
import hashlib
import json
import random
import re
import time
import wave
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from lifemate.asr import ChunkFormerASR
from lifemate.asr_eval.metrics import transcript_metrics, normalize_text_relaxed, edit_distance
from lifemate.asr_eval.sweep import default_grid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'result/chunkformer-optimization'
SEED=20261029
ACTIONS=('bật','tắt','hủy','huỷ','chuyển','đặt','nhắc','gọi','xóa','xoá','dời','không','đừng')
TIMES=('mai','nay','trước','sau','kém','rưỡi','sáng','trưa','chiều','tối','đêm')

def load(path): return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def norm(text): return normalize_text_relaxed(text)
def critical(ref,pred):
    a,b=Counter(norm(ref).split()),Counter(norm(pred).split())
    result={}
    for key,vocab in [('action',ACTIONS),('time',TIMES)]:
        relevant={t:a[t] for t in vocab if a[t]}
        result[key+'_reference_tokens']=sum(relevant.values())
        result[key+'_missing_tokens']=sum(max(0,n-b[t]) for t,n in relevant.items())
    return result

def aggregate(rows):
    summary={'utterances':len(rows),'failures':sum(bool(x.get('error')) for x in rows)}
    good=[x for x in rows if not x.get('error')]
    for key in ['relaxed_wer','relaxed_cer','wer','cer','latency_seconds']:
        summary['mean_'+key]=float(np.mean([x[key] for x in good])) if good else None
    for metric,unit in [('wer','word'),('cer','char')]:
        denominator=sum(x[unit+'_reference_count'] for x in good)
        summary['corpus_relaxed_'+metric]=sum(x[unit+'_edit_count'] for x in good)/denominator if denominator else 0
    for kind in ['action','time']:
        denom=sum(x[kind+'_reference_tokens'] for x in good)
        missing=sum(x[kind+'_missing_tokens'] for x in good)
        summary[kind+'_reference_tokens']=denom
        summary[kind+'_missing_tokens']=missing
        summary[kind+'_literal_recall']=1-missing/denom if denom else None
    summary['p95_latency_seconds']=float(np.percentile([x['latency_seconds'] for x in good],95)) if good else None
    return summary

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'selection.json').exists():
        raise SystemExit('Existing benchmark output; preserve it instead of overwriting.')
    full=load(ROOT/'data/train/train.jsonl'); val=load(ROOT/'data/validation_300/train/train.jsonl')
    excluded={x['id'] for x in val}
    pool=[x for x in full if x['id'] not in excluded]
    tune=random.Random(SEED).sample(pool,50)
    def utterances(samples,base,history=False):
        result=[]
        for s in samples:
            result.append({'sample_id':s['id'],'turn':'query','audio':str(base/s['audio']),'reference':s['audio_text']})
            if history:
                for i,h in enumerate(s.get('history',[])):
                    if h.get('audio'):
                        assert h.get('audio_text') is not None
                        result.append({'sample_id':s['id'],'turn':f'history_{i}','audio':str(base/h['audio']),'reference':h['audio_text']})
        return result
    tuning=utterances(tune,ROOT/'data/train')
    validation=utterances(val,ROOT/'data/validation_300/train',True)
    selection={'seed':SEED,'tune_ids':[x['id'] for x in tune],'validation_ids':[x['id'] for x in val],
               'tune_queries':len(tuning),'validation_utterances':len(validation),
               'source_sha256':hashlib.sha256((ROOT/'data/train/train.jsonl').read_bytes()).hexdigest(),
               'validation_sha256':hashlib.sha256((ROOT/'data/validation_300/train/train.jsonl').read_bytes()).hexdigest(),
               'selection_rule':'Lowest tune macro relaxed WER; tie-break by relaxed CER then latency. Validation not used for selection.',
               'critical_metric':'Literal token recall on fixed action/time vocabulary; diagnostic only, not semantic correctness or official score.'}
    (OUT/'selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2))
    # Inspect waveform health without modifying audio.
    health=[]
    for u in tuning+validation:
        with wave.open(u['audio'],'rb') as w:
            width=w.getsampwidth(); rate=w.getframerate(); channels=w.getnchannels()
            assert width==2, (u['audio'],width)
            pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
        health.append({'sample_id':u['sample_id'],'turn':u['turn'],'sample_rate':rate,'channels':channels,
                       'peak':float(np.max(np.abs(pcm))), 'rms':float(np.sqrt(np.mean(pcm**2))),
                       'clipped_fraction':float(np.mean(np.abs(pcm)>=32767/32768))})
    (OUT/'audio_health.json').write_text(json.dumps(health,ensure_ascii=False,indent=2))
    torch.manual_seed(SEED)
    asr=ChunkFormerASR(ROOT/'models/chunkformer-ctc-large-vie',device='cuda')
    start=time.perf_counter(); pipeline=asr._load(); pipeline.eval()
    load_seconds=time.perf_counter()-start
    # Warm-up excluded from per-utterance latency, record separately.
    start=time.perf_counter(); asr.transcribe(Path(tuning[0]['audio'])); torch.cuda.synchronize()
    warmup_seconds=time.perf_counter()-start
    print(json.dumps({'event':'loaded','load_seconds':load_seconds,'warmup_seconds':warmup_seconds,
                      'tune':len(tuning),'validation':len(validation)}),flush=True)
    def evaluate(config,items,phase):
        asr.chunk_size=config.chunk_size; asr.left_context_size=config.left_context_size; asr.right_context_size=config.right_context_size
        path=OUT/f'{phase}-{config.name}.jsonl'; rows=[]
        with path.open('w') as f:
            for i,u in enumerate(items):
                row=dict(u); start=time.perf_counter()
                try:
                    prediction=asr.transcribe(Path(u['audio'])); torch.cuda.synchronize()
                    elapsed=time.perf_counter()-start
                    row.update(prediction=prediction,latency_seconds=elapsed,error=None,
                               **transcript_metrics(u['reference'],prediction),**critical(u['reference'],prediction))
                    a,b=norm(u['reference']),norm(prediction)
                    row.update(word_reference_count=len(a.split()),word_edit_count=edit_distance(a.split(),b.split()),
                               char_reference_count=len(a),char_edit_count=edit_distance(list(a),list(b)))
                except Exception as exc:
                    row.update(error=str(exc),latency_seconds=time.perf_counter()-start)
                rows.append(row); f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush()
                if (i+1)%10==0 or i+1==len(items):
                    print(json.dumps({'event':'progress','phase':phase,'config':config.name,'done':i+1,'total':len(items)}),flush=True)
        summary={'config':config.name,**aggregate(rows)}
        (OUT/f'{phase}-{config.name}-summary.json').write_text(json.dumps(summary,indent=2))
        return summary
    grid=default_grid(); tuning_reports=[evaluate(config,tuning,'tune') for config in grid]
    if any(x['failures'] for x in tuning_reports): raise RuntimeError('Tuning failures; do not select config')
    best=min(tuning_reports,key=lambda x:(x['mean_relaxed_wer'],x['mean_relaxed_cer'],x['mean_latency_seconds']))
    chosen=next(c for c in grid if c.name==best['config'])
    (OUT/'tuning_summary.json').write_text(json.dumps(tuning_reports,indent=2))
    print(json.dumps({'event':'selected','config':chosen.name,'tuning_summary':tuning_reports}),flush=True)
    confirmed=[evaluate(grid[0],validation,'validation')]
    if chosen!=grid[0]: confirmed.append(evaluate(chosen,validation,'validation'))
    summaries=[]
    for config in [grid[0]]+([chosen] if chosen!=grid[0] else []):
        rows=load(OUT/f'validation-{config.name}.jsonl')
        summaries.append({'config':config.name,'all_audio':aggregate(rows),
                          'query_only':aggregate([r for r in rows if r['turn']=='query']),
                          'history_only':aggregate([r for r in rows if r['turn']!='query'])})
    report={'selection':selection,'load_seconds':load_seconds,'warmup_seconds':warmup_seconds,
            'tuning':tuning_reports,'selected_config':chosen.name,'validation':summaries,
            'production_config_changed':False}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'event':'complete','selected_config':chosen.name,'validation':summaries}),flush=True)

if __name__=='__main__': main()
