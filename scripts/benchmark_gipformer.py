"""Compare local FP32 Gipformer with frozen ChunkFormer validation outputs."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
import numpy as np
import torch  # preload the installed CUDA/cuDNN runtime libraries before sherpa
import sherpa_onnx
from benchmark_chunkformer import ROOT,load,aggregate
from benchmark_ctc_beam import make_row
from lifemate.asr import GipformerASR

OUT=ROOT/'result/gipformer-1.5-benchmark'
PREVIOUS=ROOT/'result/chunkformer-optimization'
MODEL=ROOT/'models/gipformer1.5-68M-rnnt'
REVISION='dd9227dcd8705c13f33bdbe59728d546ab94480f'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'predictions.jsonl').exists(): raise SystemExit('Output exists; preserve benchmark instead of overwriting.')
    items=load(PREVIOUS/'validation-chunk64_left128_right128.jsonl')
    selection=json.loads((PREVIOUS/'selection.json').read_text())
    source=ROOT/'data/validation_300/train/train.jsonl'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==selection['validation_sha256']
    assert len(items)==980 and len({x['sample_id'] for x in items})==300
    def gpu_memory():
        return int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
    before=gpu_memory()
    asr=GipformerASR(MODEL,provider='cuda',precision='fp32',num_threads=4,decoding_method='modified_beam_search')
    start=time.perf_counter(); asr._load(); load_seconds=time.perf_counter()-start
    start=time.perf_counter(); asr.transcribe(Path(items[0]['audio'])); warmup_seconds=time.perf_counter()-start
    after=gpu_memory()
    metadata={'model':'g-group-ai-lab/gipformer1.5-68M-rnnt','revision':REVISION,
              'precision':'fp32','provider':'cuda','decoding_method':'modified_beam_search','max_active_paths':4,
              'cpu_threads':4,'batch_size':1,'sample_count':300,'utterance_count':980,
              'sherpa_onnx':sherpa_onnx.__version__,'python':platform.python_version(),
              'load_seconds':load_seconds,'warmup_seconds':warmup_seconds,
              'gpu_memory_before_mib':before,'gpu_memory_after_load_and_warmup_mib':after,
              'gpu_memory_delta_mib':after-before,'validation_sha256':selection['validation_sha256'],
              'file_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(MODEL.iterdir()) if p.is_file()},
              'reference_policy':'Path/audio only to ASR; references used for scoring after decode. No LM, hotwords, or fine-tuning.'}
    (OUT/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    assert '+cuda' in sherpa_onnx.__version__ and after-before>100, 'CUDA execution not verified'
    print(json.dumps({'event':'loaded',**metadata}),flush=True)
    rows=[]
    with (OUT/'predictions.jsonl').open('w') as f:
        for i,item in enumerate(items):
            start=time.perf_counter()
            try:
                text=asr.transcribe(Path(item['audio'])); elapsed=time.perf_counter()-start
                row=make_row(item,text,elapsed)
            except Exception as exc:
                row={k:item[k] for k in ['sample_id','turn','audio','reference']};row['error']=str(exc)
            rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
            if (i+1)%25==0 or i+1==len(items):print(json.dumps({'event':'progress','done':i+1,'total':len(items)}),flush=True)
    result={'metadata':metadata,'all_audio':aggregate(rows),
            'query_only':aggregate([r for r in rows if r['turn']=='query']),
            'history_only':aggregate([r for r in rows if r['turn']!='query'])}
    (OUT/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'event':'complete','all_audio':result['all_audio'],'query_only':result['query_only']}),flush=True)
    if result['all_audio']['failures']:raise RuntimeError('Benchmark contains failed samples')

if __name__=='__main__':main()
