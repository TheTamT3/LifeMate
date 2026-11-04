"""Create the ASR comparison report from completed benchmark artifacts."""
import json
from pathlib import Path
import numpy as np
from benchmark_chunkformer import ROOT, load

OUT=ROOT/'result/gipformer-1.5-benchmark'
PREVIOUS=ROOT/'result/chunkformer-optimization'

def main():
    gip=json.loads((OUT/'report.json').read_text())
    baseline=json.loads((PREVIOUS/'report.json').read_text())['validation'][0]
    beam=json.loads((PREVIOUS/'beam_report.json').read_text())['validation']
    g=load(OUT/'predictions.jsonl'); b=load(PREVIOUS/'validation-beam16-lm030.jsonl')
    assert len(g)==len(b)==980 and not any(r['error'] for r in g)
    key=lambda r:(r['sample_id'],r['turn'])
    assert [key(r) for r in g]==[key(r) for r in b]
    gm={key(r):r for r in g};bm={key(r):r for r in b}
    diff=np.array([gm[key(r)]['relaxed_wer']-r['relaxed_wer'] for r in b if r['turn']=='query'])
    rng=np.random.default_rng(20261029); boot=np.mean(rng.choice(diff,size=(5000,len(diff)),replace=True),axis=1)
    ci=np.percentile(boot,[2.5,97.5]).tolist()
    comparison={'query_count':len(diff),'gipformer_better':int((diff<0).sum()),'gipformer_worse':int((diff>0).sum()),
                'equal':int((diff==0).sum()),'mean_wer_delta_gipformer_minus_chunkformer_lm':float(diff.mean()),'paired_bootstrap_95_ci':ci}
    (OUT/'comparison.json').write_text(json.dumps(comparison,indent=2))
    lines=['# Gipformer 1.5: benchmark trên fixed validation 300','',
           'Model: [g-group-ai-lab/gipformer1.5-68M-rnnt](https://huggingface.co/g-group-ai-lab/gipformer1.5-68M-rnnt). Recipe: [infer_onnx.py của tác giả](https://github.com/ggroup-ai-lab/gipformer/blob/main/infer_onnx.py).','',
           'Chạy ONNX FP32 trên CUDA/RTX 3090, modified_beam_search, max_active_paths=4, CPU threads=4, batch size=1. Không fine-tune, không LM ngoài, không hotwords. ChunkFormer LM có dùng text miền bài toán từ phần train riêng, nên đây là so sánh các hệ thống ASR hiện có, không phải so sánh thuần kiến trúc.','',
           f'Revision: `{gip["metadata"]["revision"]}`. Runtime: `{gip["metadata"]["sherpa_onnx"]}`. VRAM tăng sau load/warm-up: {gip["metadata"]["gpu_memory_delta_mib"]} MiB. Checksum model và dataset trong metadata.json.','',
           'Dùng đúng 300 query và 680 history (980 đoạn), cùng thứ tự và reference như benchmark ChunkFormer. Không chạy LLM/agent. Transcript chuẩn chỉ được dùng để chấm sau decode. Chưa thay ASR mặc định.','',
           'WER/CER dưới đây lowercase, bỏ dấu câu, giữ dấu tiếng Việt; chưa chuẩn hóa chữ số thành cách đọc. Không so trực tiếp với benchmark WER model card. Latency là warm per-utterance, gồm đọc audio; tách riêng model load/warm-up.','',
           '| Nhóm | Hệ thống | WER TB | Corpus WER | CER TB | Latency TB / P95 |','|---|---|---:|---:|---:|---:|']
    for group in ['query_only','history_only','all_audio']:
        for name,result in [('ChunkFormer greedy',baseline),('ChunkFormer beam + LM',beam),('Gipformer 1.5 FP32',gip)]:
            r=result[group]
            lines.append(f'| {group} | {name} | {r["mean_relaxed_wer"]:.2%} | {r["corpus_relaxed_wer"]:.2%} | {r["mean_relaxed_cer"]:.2%} | {r["mean_latency_seconds"]:.3f}s / {r["p95_latency_seconds"]:.3f}s |')
    lines+=['',f'So với ChunkFormer beam+LM trên 300 query: Gipformer tốt hơn {comparison["gipformer_better"]}, kém hơn {comparison["gipformer_worse"]}, bằng nhau {comparison["equal"]}. Chênh lệch WER TB Gipformer − ChunkFormer LM: {diff.mean()*100:+.2f} điểm %, paired bootstrap 95% CI [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}] (5.000 lần resample query).','',
            '## Từ quan trọng','', '| Hệ thống | Literal recall hành động | Literal recall thời gian |','|---|---:|---:|']
    for name,result in [('ChunkFormer greedy',baseline),('ChunkFormer beam+LM',beam),('Gipformer',gip)]:
        r=result['all_audio'];lines.append(f'| {name} | {r["action_literal_recall"]:.2%} | {r["time_literal_recall"]:.2%} |')
    lines+=['','Literal recall là diagnostic trên từ khóa cố định, không phải đúng intent/slot, không phạt mọi từ thêm; chưa có metric entity hay số tiền/giờ đã chuẩn hóa.','',
            '## Các mẫu smoke trước','', '| Sample | Reference | ChunkFormer beam+LM | Gipformer |','|---|---|---|---|']
    for sid in ['train_0035','train_0066','train_0052','train_0017','train_0025','train_0028']:
        a,c=bm[sid,'query'],gm[sid,'query']
        lines.append(f'| {sid} | {a["reference"]} | {a["prediction"]} | {c["prediction"]} |')
    lines+=['','Các lỗi hành động vẫn cần chú ý: train_0035 cần “tắt đèn” nhưng Gipformer nhận “THẮP ĐÈN”; không dùng WER thấp để kết luận yêu cầu đó đúng. Chưa chạy lại agent nên chưa có điểm end-to-end cho model mới.','',
            '## Dùng backend mới','', 'Adapter `GipformerASR` đã được thêm, dùng local files, không tự download. CLI inference, ASR eval và LangSmith experiments hỗ trợ `--asr-backend gipformer`.','',
            '```bash','PYTHONPATH=src .venv/bin/python -m lifemate.experiments \\',
            '  --root data/validation_300 \\', '  --dataset lifemate-train-validation-300-v1 \\',
            '  --experiment qwen3-4b-gipformer15-smoke \\',
            '  --asr-backend gipformer \\', '  --asr-model models/gipformer1.5-68M-rnnt \\', '  --limit 1','```','',
            'Lệnh trên là hướng dẫn cho bước end-to-end tiếp theo, chưa được chạy trong benchmark ASR này. Không dùng `--asr-decoder` CTC với model RNN-T.','',
            'Tái lập: `PYTHONPATH=src .venv/bin/python scripts/benchmark_gipformer.py`, sau đó `scripts/report_gipformer_benchmark.py` với cùng PYTHONPATH. Script benchmark từ chối ghi đè predictions cũ. Dependency/runtime: requirements-gipformer.txt.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'query':gip['query_only'],'all':gip['all_audio'],'comparison':comparison},indent=2))

if __name__=='__main__':main()
