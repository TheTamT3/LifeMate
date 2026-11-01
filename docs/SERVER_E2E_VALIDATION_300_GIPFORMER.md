# Chạy end-to-end subset 300 trên server với Gipformer 1.5

Runbook này chạy toàn bộ pipeline trên cùng server GPU:

```text
Gipformer ASR → PydanticAI → vLLM/Qwen3-4B → ToolEnv → state_hash
```

Model ASR:

```text
g-group-ai-lab/gipformer1.5-68M-rnnt
```

## 1. Vào repo và cập nhật code

```bash
ssh <your-ssh-alias>
cd /workspace/LifeMate
git pull origin main
```

## 2. Cài Miniconda và kích hoạt môi trường

Nếu server Linux x86_64 chưa có Miniconda, chạy:

```bash
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
```

Tạo môi trường `lifemate` nếu chưa có (chỉ chạy một lần):

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda create -n lifemate python=3.11 -y
```

Kích hoạt môi trường trước khi cài dependency:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate lifemate
export PYTHONPATH="$PWD/src"
```

Kiểm tra GPU:

```bash
nvidia-smi
```

## 3. Cài dependency

```bash
pip install -r requirements.txt
pip install -r requirements-gipformer.txt
python -m pip install --upgrade pip
python -m pip install vllm --extra-index-url https://download.pytorch.org/whl/cu129
vllm download-kernels
```

Kiểm tra vLLM và CUDA:

```bash
python -c "import vllm, torch; print('vLLM:', vllm.__version__); print('CUDA:', torch.cuda.is_available())"
vllm --version
```

Kiểm tra runtime Gipformer:

```bash
python - <<'PY'
import sherpa_onnx
print('sherpa_onnx:', getattr(sherpa_onnx, '__version__', 'unknown'))
print('transducer:', hasattr(sherpa_onnx.OfflineRecognizer, 'from_transducer'))
PY
```

Nếu `transducer` là `False` khi chạy CUDA, wheel đang dùng là CPU-only; cần cài wheel sherpa-onnx có CUDA provider trước khi chạy.

## 4. Chuẩn bị dữ liệu train gốc

Subset builder cần dữ liệu tại:

```text
data/train/train.jsonl
data/train/audio/
data/train/train_environment/
```

Kiểm tra:

```bash
test -f data/train/train.jsonl && echo 'train jsonl OK'
wc -l data/train/train.jsonl
```

Nếu `scripts/eda_train.py` hoặc `scripts/build_validation_subset.py` chưa có sau `git pull`, copy chúng từ máy local hoặc commit chúng trước.

### 4.1. SCP d? li?u t? local l?n server b?t k?

Ch?y t?i th? m?c g?c repo tr?n m?y local. Thay `your-ssh-alias` b?ng SSH alias
ho?c `user@hostname`, v? ???ng d?n ??ch theo server; th? m?c ??ch `data/` c?n t?n t?i.

```powershell
# Train
scp -r "./train+public_test/train+public_test/train" your-ssh-alias:/workspace/LifeMate/data/

# Public test
scp -r "./train+public_test/train+public_test/public_test" your-ssh-alias:/workspace/LifeMate/data/

# Both
scp -r "./train+public_test/train+public_test/train" "./train+public_test/train+public_test/public_test" your-ssh-alias:/workspace/LifeMate/data/
```

## 5. Tạo subset cố định 300 mẫu

```bash
PYTHONPATH=src python scripts/eda_train.py
PYTHONPATH=src python scripts/build_validation_subset.py
```

Kiểm tra:

```bash
wc -l data/validation_300/train/train.jsonl
test -f data/validation_300/train/train_tools_catalog.json && echo 'catalog OK'
test -d data/validation_300/train/train_environment && echo 'environment OK'
```

Số dòng phải là `300`.

## 6. Tải model Qwen và Gipformer

```bash
python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id='Qwen/Qwen3-4B',
    local_dir='models/qwen3-4b',
)
snapshot_download(
    repo_id='g-group-ai-lab/gipformer1.5-68M-rnnt',
    revision='dd9227dcd8705c13f33bdbe59728d546ab94480f',
    local_dir='models/gipformer1.5-68m-rnnt',
    allow_patterns=['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt', 'README.md', 'config.json'],
)
PY
```

Kiểm tra file Gipformer:

```bash
ls models/gipformer1.5-68m-rnnt/{encoder.onnx,decoder.onnx,joiner.onnx,tokens.txt}
```

## 7. Khởi động vLLM chạy nền bằng nohup

Chạy các lệnh sau trong SSH trên server GPU. `nohup` giữ vLLM chạy khi ngắt
SSH, không cần tmux. Kích hoạt môi trường `lifemate` trước khi khởi động:

```bash
cd /workspace/LifeMate
source ~/miniconda3/etc/profile.d/conda.sh
conda activate lifemate
mkdir -p logs

nohup vllm serve models/qwen3-4b \
  --served-model-name qwen3-4b \
  --host 127.0.0.1 \
  --port 8000 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.65 \
  --max-num-seqs 1 \
  --enforce-eager \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --reasoning-parser qwen3 \
  > logs/vllm.log 2>&1 < /dev/null &

echo $! > logs/vllm.pid
```

Theo dõi log khởi động:

```bash
tail -f logs/vllm.log
```

Nhấn `Ctrl+C` để thoát xem log; vLLM vẫn chạy nền. Đợi model tải xong và server
khởi động, sau đó kiểm tra từ một terminal SSH trên cùng server:

```bash
curl -f http://127.0.0.1:8000/v1/models
```

`127.0.0.1` trỏ đến máy đang chạy `curl`. Nếu chưa kết nối được, kiểm tra log,
tiến trình và cổng trước khi khởi động thêm một instance:

```bash
cd /workspace/LifeMate
tail -n 100 logs/vllm.log
ps -p "$(cat logs/vllm.pid)" -o pid,etime,args
ss -ltnp 'sport = :8000'
```

Dừng vLLM khi cần (chạy từ thư mục repo, khi PID vẫn thuộc tiến trình vLLM này):

```bash
kill "$(cat logs/vllm.pid)"
```

`nohup` không tự khởi động lại vLLM khi server reboot hoặc tiến trình bị lỗi.

## 8. Smoke test một sample

Bước này chạy full pipeline thật, không mock ASR/model/ToolEnv, và gửi trace
phân cấp lên LangSmith. Cài thêm dependency debug:

```bash
pip install -r requirements-langsmith.txt
```

LangSmith đã được cấu hình trong `.env`; script sẽ tự đọc các biến này. Lệnh
dưới đây cần vLLM đang chạy ở `127.0.0.1:8000`, model Gipformer local và
Internet để gửi trace:

```bash
PYTHONPATH=src \
python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --sample-id train_0001 \
  --model models/qwen3-4b \
  --asr-model models/gipformer1.5-68m-rnnt \
  --asr-backend gipformer \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b
```

Output gồm `project`, `run_id`, `tool_calls` và `state_hash`. Mở `run_id` trên
LangSmith sẽ thấy các child run của ASR, agent và từng tool call thật.

Lệnh `baseline.py` phía trên chỉ ghi JSONL local; không tự gửi trace.

### 8.1. Experiment 10 mẫu với trace từng row

Mỗi sample tạo một root trace riêng trên LangSmith. Model và ASR chỉ được load
một lần để tránh tốn thời gian khởi tạo lặp lại:

```bash
PYTHONPATH=src \
python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --limit 10 \
  --model models/qwen3-4b \
  --asr-model models/gipformer1.5-68m-rnnt \
  --asr-backend gipformer \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --output result/langsmith-e2e-10.jsonl
```

### 8.2. Experiment 300 mẫu với trace từng row

```bash
PYTHONPATH=src \
python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --limit 300 \
  --model models/qwen3-4b \
  --asr-model models/gipformer1.5-68m-rnnt \
  --asr-backend gipformer \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --output result/langsmith-e2e-300.jsonl
```

File JSONL chỉ là summary local; trace chi tiết nằm trên LangSmith. Không dùng
`--use-reference-text` nếu muốn chạy ASR thật trên train samples.

## 9. Chạy toàn bộ 300 mẫu

```bash
mkdir -p result

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src \
time python baseline.py \
  --root data/validation_300 \
  --split train \
  --model models/qwen3-4b \
  --asr-model models/gipformer1.5-68m-rnnt \
  --asr-backend gipformer \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --output result/gipformer-validation300-submission.jsonl \
  --limit 300
```

Kiểm tra số kết quả:

```bash
wc -l result/gipformer-validation300-submission.jsonl
```

Kết quả phải là `300`.

## 10. Các lỗi thường gặp

- `FileNotFoundError` với `encoder.onnx`: sai đường dẫn model hoặc model chưa tải đủ 4 file.
- `CPU-only`: sherpa-onnx hiện tại không có CUDA provider.
- `Connection refused 127.0.0.1:8000`: vLLM chưa chạy hoặc chạy sai port.
- `unsupported ASR backend: gipformer`: repo trên server chưa được `git pull` commit có hỗ trợ Gipformer.
- Không đọc trực tiếp `state.json`; state chỉ được truy cập qua `ToolEnv`.
