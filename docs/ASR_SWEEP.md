# ASR decode-parameter sweep

Chạy benchmark năm cấu hình ChunkFormer quanh baseline `chunk64/left128/right128`:

```powershell
$env:PYTHONPATH = "src"
\.venv-gpu\Scripts\python.exe asr_sweep.py `
  --root .\train+public_test\train+public_test `
  --split train `
  --asr-model C:\models\chunkformer-ctc-large-vie `
  --output-dir .\result\asr_sweep_100 `
  --report .\result\asr_sweep_100_report.json `
  --limit 100 --device cuda --batch-size 4
```

Mỗi cấu hình có một file prediction/report riêng; file tổng hợp chứa WER, CER,
relaxed WER/CER, fuzzy F1 và latency. Chọn cấu hình có `average_relaxed_wer`
thấp nhất, sau đó chạy lại trên tập lớn hơn trước khi dùng trong baseline.
