# Chạy LifeMate trên Google Colab

Tài liệu này hướng dẫn chạy baseline trên Colab GPU. Model được tải trong giai đoạn phát triển; khi chấm chính thức, inference phải chạy offline theo rule của cuộc thi.

## 1. Bật GPU

Trong Colab chọn:

`Runtime → Change runtime type → T4 GPU`

Kiểm tra:

```python
!nvidia-smi
```

## 2. Clone repository

### Repository public

```python
%cd /content
!rm -rf LifeMate
!git clone https://github.com/TheTamT3/LifeMate.git
%cd /content/LifeMate
```

### Repository private

Tạo GitHub Personal Access Token có quyền đọc repository. Trong Colab mở biểu tượng chìa khóa, tạo secret tên `GITHUB_TOKEN`, rồi chạy:

```python
import subprocess
from google.colab import userdata

token = userdata.get("GITHUB_TOKEN")
assert token, "Chưa cấu hình GITHUB_TOKEN trong Colab Secrets"

url = f"https://x-access-token:{token}@github.com/TheTamT3/LifeMate.git"
subprocess.run(["git", "clone", url, "/content/LifeMate"], check=True)

del token
del url
```

Kiểm tra đúng phiên bản mới nhất:

```python
%cd /content/LifeMate
!git log -1 --oneline
```

## 3. Cài dependencies

Khởi động lại runtime trước khi cài nếu phiên Colab đã cài nhiều package:

`Runtime → Restart session`

Sau đó chạy:

```python
%cd /content/LifeMate
!pip install -q -r requirements.txt
!pip install -q huggingface_hub bitsandbytes
```

Repo không ép phiên bản Torch. Colab sẽ sử dụng Torch CUDA có sẵn trong runtime. Trước mắt dùng Qwen3-1.7B nguyên gốc; code vẫn hỗ trợ load 4-bit nếu cần.

Kiểm tra:

```python
import torch
import transformers

print("Torch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())
print("Transformers:", transformers.__version__)
```

`pip` có thể hiển thị warning về `diffusers`, `gradio`, `google-adk` hoặc `opentelemetry`. Đây là package có sẵn của Colab, không được LifeMate sử dụng. Nếu CUDA trả về `True`, có thể tiếp tục.

## 4. Tải model từ Hugging Face

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-1.7B",
    local_dir="/content/models/qwen3-1.7b",
)

snapshot_download(
    repo_id="khanhld/chunkformer-ctc-large-vie",
    local_dir="/content/models/chunkformer-ctc-large-vie",
)
```

Mặc định LLM chạy FP16, không quantize. Nếu GPU thiếu VRAM, thêm flag
`--quantize` vào lệnh baseline để bật 4-bit NF4.

Có thể lưu model vào Google Drive để không tải lại sau mỗi phiên:

```python
from google.colab import drive
drive.mount("/content/drive")
```

Sau đó thay `/content/models/...` bằng đường dẫn trong `/content/drive/MyDrive/...`.

## 5. Chuẩn bị dataset

Dataset không nằm trong Git repo. Upload file zip dataset lên Google Drive rồi giải nén:

```python
!mkdir -p /content/data
!unzip -q "/content/drive/MyDrive/train+public_test.zip" -d /content/data
!find /content/data -maxdepth 3 -type f | head -30
```

Kiểm tra vị trí thực tế của file dữ liệu:

```python
!find /content/data -name train.jsonl
```

`DATA_ROOT` phải là thư mục chứa trực tiếp hai thư mục:

```text
train/
public_test/
```

Với file zip ở trên, đường dẫn thường là:

```python
%env DATA_ROOT=/content/data/train+public_test/train+public_test
!test -f "$DATA_ROOT/train/train.jsonl" && echo "DATA_ROOT OK"
!test -f "$DATA_ROOT/train/train_tools_catalog.json" && echo "CATALOG OK"
```

Nếu lệnh `find` trả về đường dẫn khác, hãy lấy phần thư mục ngay trước `/train/train.jsonl` làm `DATA_ROOT`. Không đặt `DATA_ROOT` trỏ trực tiếp vào thư mục `train/`, vì chương trình sẽ tự nối thêm `train/` theo `--split train`.

## 6. Chạy train smoke test

Train có trường `audio_text`, nên bước này kiểm tra Qwen, prompt, ToolEnv và output JSONL mà chưa cần ASR thật:

```python
%env PYTHONPATH=/content/LifeMate/src
!python /content/LifeMate/baseline.py \
  --root "$DATA_ROOT" \
  --split train \
  --model /content/models/qwen3-1.7b \
  --asr-model /content/models/chunkformer-ctc-large-vie \
  --output /content/result/train_smoke.jsonl \
  --limit 1
```

Kiểm tra output:

```python
!cat /content/result/train_smoke.jsonl
```

Mỗi dòng phải có đúng các trường chính:

```json
{"id":"...", "tool_calls":[], "state_hash":"..."}
```

## 7. Chạy public smoke test có ASR

```python
!python /content/LifeMate/baseline.py \
  --root "$DATA_ROOT" \
  --split public_test \
  --model /content/models/qwen3-1.7b \
  --asr-model /content/models/chunkformer-ctc-large-vie \
  --output /content/result/public_smoke.jsonl \
  --limit 1
```

Nếu smoke test thành công, chạy toàn bộ public test:

```python
!time python /content/LifeMate/baseline.py \
  --root "$DATA_ROOT" \
  --split public_test \
  --model /content/models/qwen3-1.7b \
  --asr-model /content/models/chunkformer-ctc-large-vie \
  --output /content/result/submission.jsonl
```

File kết quả:

```text
/content/result/submission.jsonl
```

## 8. Xử lý lỗi thường gặp

### Git yêu cầu username/password

Repository đang private. Dùng `GITHUB_TOKEN` theo mục 2, không dùng password GitHub thông thường.

### `No module named lifemate`

```python
%env PYTHONPATH=/content/LifeMate/src
```

### `No module named accelerate`

```python
!pip install -q accelerate==1.10.1
```

### Không load được ChunkFormer

Kiểm tra đường dẫn model có các file như `config.yaml`, `pytorch_model.bin`, `vocab.txt`:

```python
!ls /content/models/chunkformer-ctc-large-vie
```

### Hết VRAM

- Chạy train và public ở các cell riêng.
- Không load nhiều model copy cùng lúc.
- Restart runtime trước khi chạy lại.
- Dùng GPU Colab lớn hơn nếu cần.

## 9. Quy tắc quan trọng

- Không commit model weights, dataset hoặc `state.json` lên GitHub.
- Agent chỉ truy cập app state qua `ToolEnv`.
- Không gọi OpenAI, ElevenLabs, Hugging Face API hoặc dịch vụ ngoài trong inference chính thức.
- Kết quả nộp phải là UTF-8 JSONL với `id`, `tool_calls`, `state_hash`.
Memory note: the baseline now generates at most 128 new tokens, truncates each
prompt to 4096 tokens, and disables the generation KV cache to reduce CUDA OOM
risk on a 16 GB Colab GPU. Restart the runtime and smoke-test with `--limit 1`
if the GPU still reports out-of-memory.

## Qwen3-ASR-1.7B evaluation

Install the official local inference package and download the ASR checkpoint:

```python
!pip install -q qwen-asr

from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3-ASR-1.7B",
    local_dir="/content/models/qwen3-asr-1.7b",
)
```

Run the existing ASR evaluator with the Qwen backend:

```python
%env PYTHONPATH=/content/LifeMate/src
!python /content/LifeMate/asr_eval.py \
  --root "$DATA_ROOT" \
  --split train \
  --asr-model /content/models/qwen3-asr-1.7b \
  --asr-backend qwen3 \
  --output /content/result/qwen3_asr_predictions.jsonl \
  --report /content/result/qwen3_asr_report.json \
  --limit 20 --device cuda --batch-size 1
```

Use `--batch-size 1` first to reduce VRAM usage. If the model loads correctly,
try `2` or `4` and compare the report. The model and evaluator remain offline
after the checkpoint has been downloaded.

To use Qwen3-ASR in the complete LifeMate baseline, add the backend flag:

```python
!python /content/LifeMate/baseline.py \
  --root "$DATA_ROOT" --split public_test \
  --model /content/models/qwen3-1.7b \
  --asr-model /content/models/qwen3-asr-1.7b \
  --asr-backend qwen3 \
  --output /content/result/qwen3_asr_submission.jsonl --limit 1
```

## ASR model comparison

The evaluator also supports the following local backends:

- `parakeet`: NeMo Parakeet Vietnamese checkpoint
- `whisper`: Whisper-family checkpoints, including Whisper Turbo and BuzzASR

For Parakeet, install NeMo and download `nmcuong/parakeet-tdt-0.6b-v3-vietnamese`:

```python
!pip install -q "nemo_toolkit[asr]"
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="nmcuong/parakeet-tdt-0.6b-v3-vietnamese",
    local_dir="/content/models/parakeet-vietnamese",
)
```

For Whisper Turbo or BuzzASR, Transformers is already installed:

```python
snapshot_download(
    repo_id="openai/whisper-large-v3-turbo",
    local_dir="/content/models/whisper-large-v3-turbo",
)
# Or use: repo_id="BuzzASR/vietnamese"
```

Run each model on the same samples:

```python
%env PYTHONPATH=/content/LifeMate/src
!python /content/LifeMate/asr_eval.py \
  --root "$DATA_ROOT" --split train \
  --asr-model /content/models/parakeet-vietnamese \
  --asr-backend parakeet \
  --output /content/result/parakeet_predictions.jsonl \
  --report /content/result/parakeet_report.json \
  --limit 100 --device cuda --batch-size 1

!python /content/LifeMate/asr_eval.py \
  --root "$DATA_ROOT" --split train \
  --asr-model /content/models/whisper-large-v3-turbo \
  --asr-backend whisper \
  --output /content/result/whisper_turbo_predictions.jsonl \
  --report /content/result/whisper_turbo_report.json \
  --limit 100 --device cuda --batch-size 1
```

Compare `average_relaxed_wer`, `average_fuzzy_token_f1`, and latency in the
generated report files. Use the same 100 samples for every model.
