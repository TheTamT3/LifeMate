# Chạy baseline với PydanticAI và vLLM

Baseline mới không load Qwen bằng Transformers trong process chính. Qwen được
chạy bởi vLLM trên cùng máy/Colab, còn LifeMate gọi endpoint local qua
PydanticAI.

## 1. Cài dependency

Trên Linux/Colab có GPU:

```bash
pip install -r requirements.txt
pip install vllm
```

Trên Windows local chỉ cần cài dependency Python để chạy unit test; vLLM không
bắt buộc phải chạy ở máy RTX 3050 4 GB.

## 2. Chuẩn bị model

Đặt bản local của checkpoint tại `/content/models/qwen3-4b` hoặc đường dẫn
tương ứng trên server:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-4B",
    local_dir="/content/models/qwen3-4b",
)
```

Inference chính thức phải dùng checkpoint đã tải sẵn; sau khi tải xong có thể
ngắt mạng.

## 3. Khởi động vLLM

Chạy process này trong một terminal/cell riêng:

```bash
vllm serve /content/models/qwen3-4b \
  --served-model-name qwen3-4b \
  --host 127.0.0.1 \
  --port 8000 \
  --max-model-len 16384 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --reasoning-parser qwen3
```

`qwen3_xml` là parser dành cho tool-call XML của Qwen3. Nếu phiên bản vLLM
đang dùng không có parser này, kiểm tra danh sách parser của chính phiên bản đó
trước khi chạy; không tự đổi sang parser của model khác.

Kiểm tra server đang chạy:

```bash
curl http://127.0.0.1:8000/v1/models
```

Lệnh kiểm tra chỉ dùng trong môi trường phát triển; inference vẫn chỉ gọi
`127.0.0.1`, không gọi dịch vụ bên ngoài.

## 4. Chạy baseline

```bash
PYTHONPATH=src python baseline.py \
  --root /content/data/train+public_test/train+public_test \
  --split train \
  --model /content/models/qwen3-4b \
  --asr-model /content/models/chunkformer-ctc-large-vie \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --output /content/result/submission.jsonl \
  --limit 1
```

`--model` hiện được giữ để tương thích CLI cũ; model LLM thực tế được chọn bởi
`--llm-model-name` ở vLLM. ASR vẫn dùng `--asr-model` và `--asr-backend` như
trước.

Chạy public test bằng cách đổi `--split public_test` và bỏ `--limit`. Mỗi dòng
output phải có đúng `id`, `tool_calls`, `state_hash`.

## 5. Quy tắc offline

- Không dùng URL LLM ngoài `localhost`, `127.0.0.1` hoặc `::1`.
- Không gọi OpenAI, ElevenLabs, Hugging Face Inference API hay dịch vụ ngoài tại
  inference.
- Không đọc `state.json`; app state chỉ đi qua `ToolEnv`.
- Nếu vLLM chưa chạy, baseline phải dừng với lỗi kết nối thay vì tự chuyển sang
  provider remote.
