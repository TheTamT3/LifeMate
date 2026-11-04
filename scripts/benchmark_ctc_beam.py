"""Evaluate beam/LM on the same tuning split; confirm winner on validation.
LM text excludes both 300 validation IDs and 50 tuning IDs. No labels at decode.
"""
from __future__ import annotations
import json
import hashlib
import time
from pathlib import Path
import numpy as np
import torch
from benchmark_chunkformer import ROOT, OUT, load, aggregate, critical, norm
from lifemate.asr import ChunkFormerASR
from lifemate.asr_eval.ctc_decoder import BackoffLM, prefix_beam_search
from lifemate.asr_eval.metrics import transcript_metrics,edit_distance

def make_row(item,prediction,seconds):
    row={k:item[k] for k in ['sample_id','turn','audio','reference']}
    row.update(prediction=prediction,latency_seconds=seconds,error=None,
               **transcript_metrics(item['reference'],prediction),**critical(item['reference'],prediction))
    a,b=norm(item['reference']),norm(prediction)
    row.update(word_reference_count=len(a.split()),word_edit_count=edit_distance(a.split(),b.split()),
               char_reference_count=len(a),char_edit_count=edit_distance(list(a),list(b)))
    return row

def main():
    selection=json.loads((OUT/'selection.json').read_text())
    dev=load(OUT/'tune-chunk64_left128_right128.jsonl')
    validation=load(OUT/'validation-chunk64_left128_right128.jsonl')
    excluded=set(selection['tune_ids'])|set(selection['validation_ids'])
    corpus_samples=[s for s in load(ROOT/'data/train/train.jsonl') if s['id'] not in excluded]
    texts=[]
    for s in corpus_samples:
        texts.append(s['audio_text'])
        texts.extend(h['audio_text'] for h in s.get('history',[]) if h.get('role')=='user' and h.get('audio_text'))
    forbidden_texts={norm(item['reference']) for item in dev+validation}
    removed=sum(norm(text) in forbidden_texts for text in texts)
    texts=[text for text in texts if norm(text) not in forbidden_texts]
    lm=BackoffLM(texts)
    lm_meta={'training_sample_ids':[s['id'] for s in corpus_samples],'training_samples':len(corpus_samples),
             'exact_heldout_texts_removed':removed,'training_utterances':len(texts),'word_vocabulary':len(lm.unigrams),'forbidden_ids':sorted(excluded)}
    assert not set(lm_meta['training_sample_ids'])&excluded
    (OUT/'lm_training.json').write_text(json.dumps(lm_meta,indent=2))
    (OUT/'word_lm.json').write_text(json.dumps(lm.to_dict(),ensure_ascii=False))
    asr=ChunkFormerASR(ROOT/'models/chunkformer-ctc-large-vie',device='cuda')
    model=asr._load(); model.eval(); labels=[model.char_dict[i] for i in range(len(model.char_dict))]
    def acoustic(item):
        char_dict=model.char_dict
        try:
            model.char_dict=None
            start=time.perf_counter()
            logits=model.endless_decode(audio_path=item['audio'],chunk_size=64,left_context_size=128,
                                        right_context_size=128,total_batch_duration=14400,return_timestamps=False)
            torch.cuda.synchronize()
            return logits.float().cpu().numpy(),time.perf_counter()-start
        finally: model.char_dict=char_dict
    configs=[{'name':'beam16-no-lm','alpha':0.,'beta':0.},
             {'name':'beam16-lm005','alpha':.05,'beta':0.},
             {'name':'beam16-lm015','alpha':.15,'beta':.5},
             {'name':'beam16-lm030','alpha':.3,'beta':1.}]
    all_rows={c['name']:[] for c in configs}
    for i,item in enumerate(dev):
        logits,acoustic_seconds=acoustic(item)
        for cfg in configs:
            start=time.perf_counter()
            text=prefix_beam_search(logits,labels,lm=lm if cfg['alpha'] else None,alpha=cfg['alpha'],beta=cfg['beta'])
            all_rows[cfg['name']].append(make_row(item,text,acoustic_seconds+time.perf_counter()-start))
        if (i+1)%10==0: print(json.dumps({'event':'beam_tune','done':i+1,'total':len(dev)}),flush=True)
    reports=[]
    for cfg in configs:
        rows=all_rows[cfg['name']]
        (OUT/f'tune-{cfg["name"]}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        reports.append({**cfg,**aggregate(rows)})
    baseline={'name':'greedy',**aggregate(dev)}
    best=min([baseline,*reports],key=lambda c:(c['mean_relaxed_wer'],c['mean_relaxed_cer'],c['mean_latency_seconds']))
    report={'baseline_tune':baseline,'candidates_tune':reports,'selected':best['name'],'lm_training_samples':len(corpus_samples)}
    (OUT/'beam_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'event':'beam_selected',**report}),flush=True)
    if best['name']=='greedy': return
    cfg=next(c for c in configs if c['name']==best['name'])
    artifact={'version':1,'beam_width':16,'token_top_k':20,'alpha':cfg['alpha'],'beta':cfg['beta'],
              'vocab_sha256':hashlib.sha256((ROOT/'models/chunkformer-ctc-large-vie/vocab.txt').read_bytes()).hexdigest(),
              'language_model':lm.to_dict(),'training_source_sha256':selection['source_sha256'],
              'selection':'50 tuning samples disjoint from 300 validation samples; exact heldout text removed'}
    (OUT/'decoder.json').write_text(json.dumps(artifact,ensure_ascii=False))
    rows=[]
    with (OUT/f'validation-{cfg["name"]}.jsonl').open('w') as f:
        for i,item in enumerate(validation):
            logits,acoustic_seconds=acoustic(item)
            start=time.perf_counter()
            text=prefix_beam_search(logits,labels,lm=lm if cfg['alpha'] else None,alpha=cfg['alpha'],beta=cfg['beta'])
            row=make_row(item,text,acoustic_seconds+time.perf_counter()-start)
            rows.append(row); f.write(json.dumps(row,ensure_ascii=False)+'\n'); f.flush()
            if (i+1)%25==0 or i+1==len(validation):
                print(json.dumps({'event':'beam_validation','done':i+1,'total':len(validation)}),flush=True)
    report['validation']={'all_audio':aggregate(rows),'query_only':aggregate([r for r in rows if r['turn']=='query']),
                          'history_only':aggregate([r for r in rows if r['turn']!='query'])}
    (OUT/'beam_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'event':'beam_complete',**report}),flush=True)

if __name__=='__main__': main()
