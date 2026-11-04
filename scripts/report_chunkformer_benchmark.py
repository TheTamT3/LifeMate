"""Summarise completed local ChunkFormer experiments without inference."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
from benchmark_chunkformer import ROOT,OUT,load

def main():
    chunk=json.loads((OUT/'report.json').read_text()); beam=json.loads((OUT/'beam_report.json').read_text())
    if 'validation' not in beam: raise SystemExit('Beam validation is still running')
    baseline=chunk['validation'][0]; selected=beam['validation']
    old=load(OUT/'validation-chunk64_left128_right128.jsonl'); new=load(OUT/f'validation-{beam["selected"]}.jsonl')
    assert len(old)==len(new)==980
    keys=lambda r:(r['sample_id'],r['turn'])
    assert [keys(r) for r in old]==[keys(r) for r in new]
    assert not any(r['error'] for r in old+new)
    oldmap={keys(r):r for r in old};newmap={keys(r):r for r in new}
    differences=np.array([newmap[keys(r)]['relaxed_wer']-r['relaxed_wer'] for r in old if r['turn']=='query'])
    rng=np.random.default_rng(20261029)
    bootstrap=np.mean(rng.choice(differences,size=(5000,len(differences)),replace=True),axis=1)
    ci=np.percentile(bootstrap,[2.5,97.5]).tolist()
    health=json.loads((OUT/'audio_health.json').read_text())
    audit={'query_pairs':len(differences),'improved':int((differences<0).sum()),'worse':int((differences>0).sum()),
           'unchanged':int((differences==0).sum()),'mean_wer_delta':float(differences.mean()),'paired_bootstrap_95_ci':ci,
           'artifact_sha256':hashlib.sha256((OUT/'decoder.json').read_bytes()).hexdigest()}
    (OUT/'comparison.json').write_text(json.dumps(audit,indent=2))
    lines=['# ChunkFormer: kết quả tối ưu ASR','',
           'Chạy offline trên RTX 3090, batch size 1. Không chạy agent/LLM, không dùng API ASR. Chưa thay default production; decoder mới bật bằng flag riêng.','',
           '## Thiết kế đánh giá','',
           '- Tune trên 50 query từ phần train ngoài 300 validation; chọn cấu hình chỉ theo kết quả tune.',
           '- LM n-gram học từ 1.195 mẫu ngoài cả tune và validation. Lọc thêm câu trùng nguyên văn (sau chuẩn hóa) với toàn bộ audio của hai nhóm.',
           '- Xác nhận baseline và ứng viên trên đủ 300 query + 680 history = 980 đoạn audio. Không cung cấp transcript chuẩn cho model lúc decode.',
           '- WER/CER trong bảng đã lowercase và bỏ dấu câu, vẫn giữ dấu tiếng Việt. Chưa chuẩn hóa chữ số ↔ cách đọc; vì vậy lỗi như “6” ↔ “sáu” vẫn có thể bị tính lỗi.',
           '- WER trung bình là trung bình mỗi đoạn; corpus WER cộng tổng edit distance rồi chia tổng số từ. Các metric này không phải điểm cuộc thi.',
           '- Latency warm đo serial, đã synchronize CUDA; không bao gồm load model. Không suy ra end-to-end sẽ đạt <30s.','',
           '## Sweep chunk/context trên 50 query','',
           '| Chunk / left / right | WER TB | CER TB | Latency TB |','|---|---:|---:|---:|']
    for r in chunk['tuning']:
        lines.append(f'| {r["config"]} | {r["mean_relaxed_wer"]:.2%} | {r["mean_relaxed_cer"]:.2%} | {r["mean_latency_seconds"]:.3f}s |')
    lines+=['','Các cấu hình 64/128/128, 32/128/128, 96/128/128 và 64/256/256 bằng nhau trên tune. Chọn 96 theo latency tie-break chỉ là chênh lệch nhỏ; xác nhận validation không cải thiện. Giữ baseline chunk64.','',
            '## Beam search và LM trên 50 query','', '| Decoder | WER TB | CER TB | Latency TB |','|---|---:|---:|---:|']
    for r in [beam['baseline_tune'],*beam['candidates_tune']]:
        lines.append(f'| {r["name"]} | {r["mean_relaxed_wer"]:.2%} | {r["mean_relaxed_cer"]:.2%} | {r["mean_latency_seconds"]:.3f}s |')
    lines+=['',f'Ứng viên được chọn: `{beam["selected"]}`, beam width 16, top-k 20, alpha 0.3, beta 1.0, chunk 64/128/128.','',
            '## Xác nhận trên validation','', '| Nhóm | Decoder | WER TB | Corpus WER | CER TB | Latency TB / P95 |','|---|---|---:|---:|---:|---:|']
    for group in ['query_only','history_only','all_audio']:
        for name,report in [('greedy',baseline),(beam['selected'],selected)]:
            r=report[group]
            lines.append(f'| {group} | {name} | {r["mean_relaxed_wer"]:.2%} | {r["corpus_relaxed_wer"]:.2%} | {r["mean_relaxed_cer"]:.2%} | {r["mean_latency_seconds"]:.3f}s / {r["p95_latency_seconds"]:.3f}s |')
    lines+=['',f'300 query: {audit["improved"]} tốt hơn, {audit["worse"]} kém hơn, {audit["unchanged"]} bằng nhau theo WER. Chênh lệch trung bình mới − cũ: {audit["mean_wer_delta"]*100:+.2f} điểm %. Bootstrap paired 95% CI: [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}] điểm % (5.000 lần resample theo query).','',
            '## Thông tin quan trọng trong lời nói','', '| Nhóm | Literal recall hành động | Literal recall thời gian |','|---|---:|---:|']
    for name,report in [('greedy',baseline),(beam['selected'],selected)]:
        r=report['all_audio'];lines.append(f'| {name} | {r["action_literal_recall"]:.2%} | {r["time_literal_recall"]:.2%} |')
    lines+=['','Literal recall chỉ kiểm tra số lần giữ lại các từ trong danh sách cố định (bật/tắt/đặt/gọi/không…; mai/nay/trước/sau/kém…). Không đo đúng ngữ nghĩa, không phạt mọi từ thêm, không chuẩn hóa lượng tiền hay giờ. Tên riêng được xem bằng các ví dụ bên dưới, chưa có metric entity chuẩn.','',
            '## Ví dụ ở các mẫu smoke trước','', '| Sample | Reference | Greedy | Beam + LM |','|---|---|---|---|']
    for sid in ['train_0035','train_0066','train_0052','train_0017','train_0025','train_0028']:
        a,b=oldmap[sid,'query'],newmap[sid,'query']
        lines.append(f'| {sid} | {a["reference"]} | {a["prediction"]} | {b["prediction"]} |')
    lines+=['','LM có thể ưu tiên cụm từ phổ biến và làm sai tên riêng hoặc yêu cầu hiếm; không phải mọi query đều cải thiện. Cần đánh giá agent riêng trước khi kết luận tăng điểm cuộc thi.','',
            '## Audio và triển khai','',
            f'Đã đọc {len(health)} audio (50 tune + 980 validation): tất cả 16kHz mono; {sum(x["clipped_fraction"]>.01 for x in health)} đoạn có clipping >1%, {sum(x["rms"]<.005 for x in health)} đoạn có RMS <0.005. Chưa áp dụng denoise/normalize vì chưa có bằng chứng cần thiết. Chưa đánh giá nhiễu/giọng bằng nghe thủ công.', '',
            '`decoder.json` chứa LM đã học và thông số decoder; artifact có SHA256 trong comparison.json. Adapter kiểm tra vocab checksum, không đọc label/transcript ở runtime.','',
            'Để dùng trong experiment (chỉ chạy khi chủ động gọi):','',
            '```bash','PYTHONPATH=src .venv/bin/python -m lifemate.experiments \\',
            '  --root data/validation_300 \\', '  --dataset lifemate-train-validation-300-v1 \\',
            '  --experiment qwen3-4b-chunkformer-beam-lm \\',
            '  --asr-decoder result/chunkformer-optimization/decoder.json \\', '  --limit 1','```','',
            'Tái lập: `scripts/benchmark_chunkformer.py`, `scripts/benchmark_ctc_beam.py`, `scripts/report_chunkformer_benchmark.py` (PYTHONPATH=src). Script baseline từ chối ghi đè kết quả đã có; lưu/đổi tên thư mục output cũ nếu muốn chạy lại.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
