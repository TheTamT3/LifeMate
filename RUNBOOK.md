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
  --tool-call-parser hermes \
  --reasoning-parser qwen3
```

`Qwen/Qwen3-4B` dùng JSON bên trong thẻ `<tool_call>`, phù hợp với parser
`hermes` theo tài liệu Qwen: https://qwen.readthedocs.io/en/latest/framework/function_call.html.
Không dùng `qwen3_xml` với chat template mặc định của checkpoint này vì parser
đó chờ cú pháp `<function=...>` và có thể làm mất tool call.

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

## Smoke test trên server hiện tại

Môi trường riêng: `/workspace/LifeMate/.venv` (Python 3.11). Dùng
`requirements-smoke.txt` cho Qwen3-4B + ChunkFormer; file này bỏ `qwen-asr`
(tùy chọn, xung đột với các pin Transformers/Accelerate hiện tại) và pin các
package telemetry tương thích với PydanticAI 1.16.

```bash
cd /workspace/LifeMate
source .venv/bin/activate
# Khi cần cài lại, dùng hardlink để cache không nhân đôi dung lượng:
UV_NO_CACHE=false UV_LINK_MODE=hardlink UV_CACHE_DIR="$PWD/.cache/uv-smoke" \
  uv pip install --python .venv/bin/python -r requirements-smoke.txt

curl http://127.0.0.1:8000/v1/models
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src python baseline.py \
  --root data --split public_test --limit 1 \
  --model models/qwen3-4b \
  --asr-model models/chunkformer-ctc-large-vie \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --output result/smoke-public-test.jsonl
```

Do đĩa server nhỏ, các đường dẫn trong `models/` hiện là symlink tới
`/dev/shm/lifemate-models/` (RAM). Checkpoint sẽ mất khi restart máy và phải tải
lại trước khi chạy. `.venv` và dữ liệu public test nằm trên đĩa.

vLLM được quản lý bằng `supervisorctl status lifemate-vllm`;
log tại `/var/log/portal/lifemate-vllm.log`. Cấu hình smoke dùng
`--gpu-memory-utilization 0.65 --max-num-seqs 1 --enforce-eager` để chừa VRAM
cho ASR trên RTX 3090 24 GB.

## Quan sát end-to-end bằng LangSmith (debug có mạng)

File `.env` tại root repo đã có sẵn và được Git bỏ qua. Điền cấu hình:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=lifemate-debug
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
# LANGSMITH_WORKSPACE_ID=<workspace-id-if-required>
```

CLI tự đọc `.env` từ root repo; biến môi trường đã export được ưu tiên.
Không cần sửa API key trong code. `.env.example` là mẫu không chứa secret.
Dependency `langsmith` và `python-dotenv` nằm trong cả hai file requirements.
Giữ nguyên lệnh baseline ở phần smoke test, rồi mở project `lifemate-debug`
trong LangSmith để xem từng trace `lifemate.sample`, lọc theo metadata
`sample_id` / `split`.

```text
lifemate.sample
  tool_env.initialize
  asr.transcribe             # đường dẫn audio, transcript, thời gian/lỗi
  agent.prepare              # số tool, kích thước prompt
  agent.run
    vllm.chat                # từng request: prompt, response, usage/token, lỗi
    <tool name>              # arguments, kết quả ToolEnv, thời gian/lỗi
  result.serialize           # id, tool_calls, state_hash
```

Root trace ghi `latency_seconds` và `latency_budget_passed` với ngưỡng 30 giây.
Đây là cờ quan sát, không phải cơ chế timeout hay tối ưu tốc độ. Lỗi provider
bị agent bắt vẫn được đánh dấu trên trace agent và root. Trace được gửi nền;
CLI flush tối đa 3 giây sau khi hoàn tất hoặc gặp lỗi trong vòng lặp dataset.

Tracing bật sẽ gửi transcript, prompt/context/history, phản hồi LLM và
arguments/kết quả tool tới LangSmith. Không tự upload audio thô, dataset label
hay toàn bộ state môi trường. LLM/ASR vẫn inference local. Chế độ debug này
có gọi dịch vụ ngoài để gửi telemetry; khi chạy offline/chấm chính thức đặt
`LANGSMITH_TRACING=false`. Khi tắt, LifeMate không tạo LangSmith client hay
trace request. Dùng API key thuộc region tương ứng với endpoint đã cấu hình.

Tham khảo SDK chính thức: https://github.com/langchain-ai/langsmith-sdk/tree/main/python

### Cấu trúc input Qwen3

System đầu tiên chứa vai trò, rules và khối `<sample_context>` (không có
`installed_apps`). History được chuyển thành message user/assistant và tool
call/result có ID khớp nhau; audio của user trong history được nhận dạng bằng
cùng backend ASR. User cuối chỉ chứa transcript hiện tại. Tool schema chỉ gửi
qua PydanticAI; chat template của checkpoint tự chèn chúng vào system theo
format Qwen3. Không lặp `available_tools` trong message.

Tham khảo: https://qwen.readthedocs.io/en/latest/getting_started/concepts.html#tool-calling

### LangSmith validation experiments (train)

Dùng train như validation cố định, không dùng để huấn luyện trong workflow này.
Dataset `lifemate-train-validation-v1` chứa 1 row/sample; đáp án gồm tool calls và
hash canonical của state đầy đủ sau replay các tool calls chuẩn trên ToolEnv ban đầu. Không upload audio nhị phân; input chứa
đường dẫn audio, context và history. Label tách riêng ở reference outputs;
`audio_text` chuẩn bị loại bỏ để luôn đo ASR thật. Cần bộ data local để chạy lại.

```bash
# Đồng bộ dataset, không inference
PYTHONPATH=src .venv/bin/python -m lifemate.experiments --sync-only

# Smoke mặc định 1 sample; chọn sample cụ thể và đặt tên giải pháp
PYTHONPATH=src .venv/bin/python -m lifemate.experiments \
  --sample-id train_0002 --limit 1 \
  --experiment qwen3-4b-baseline-smoke \
  --output result/train-experiment-smoke.json
```

Mỗi lần chạy tạo experiment mới với hậu tố riêng. Mở URL được in ra, chọn row
trong bảng kết quả experiment để xem trace target → lifemate.sample → ASR /
agent / LLM / tools. Các child span kế thừa project của experiment.
Dataset có UUID row ổn định; đồng bộ lại không tạo trùng. Nếu source thay đổi,
phải dùng tên dataset mới. Experiment lưu source/code SHA256, git revision,
seed, model, ASR và danh sách sample để phân biệt các baseline.

Feedback: `tool_calls_exact` so khớp toàn bộ danh sách theo thứ tự và arguments;
`state_hash_match` so hash theo hàm canonical chính thức; `under_30s` kiểm tra
latency end-to-end của sample; `pipeline_ok` đánh dấu lỗi pipeline/provider.
Đây là các metric baseline, không thay thế scorer chính thức. Số request LLM,
input/output tokens và latency có trong output `metrics` của từng row.
Ngưỡng 30 giây hiện được chấm sau khi chạy, chưa ngắt inference tại deadline.
Không cần LLM-as-judge hay API LLM trả phí cho evaluator.

Mặc định chỉ infer 1 sample, concurrency 1. Chỉ tăng `--limit` khi muốn chạy
validation lớn hơn; việc sync đủ dataset không chạy ASR/LLM trên toàn bộ train.

### Fixed validation subset: 300 samples

Subset nằm tại `data/validation_300/`, giữ cấu trúc split `train` để tương thích
ToolEnv. `train/train.jsonl` chứa đúng 300 mẫu gốc cùng label; audio query/history,
environment và catalog nằm trong cùng root, không phụ thuộc symlink tới full train.
`manifest.json` cố định danh sách ID, seed và checksum; `distribution.csv` và
`README.md` ghi coverage và độ lệch phân phối. Tạo subset bằng
`.venv/bin/python scripts/build_validation_subset.py` sau khi chạy EDA; script từ
chối ghi đè subset đã có. Cần SciPy có `scipy.optimize.milp`.

Để dùng subset cho experiment, đặt `--root data/validation_300` và dùng dataset
riêng `--dataset lifemate-train-validation-300-v1`; giữ `--limit 1` cho smoke test,
chỉ đặt `--limit 300` khi muốn chạy toàn bộ subset. Không dùng lại tên dataset
của full train vì checksum nguồn khác nhau.

### ChunkFormer beam search + n-gram LM (opt-in)

Greedy mặc định giữ nguyên. Có thể bật decoder đã benchmark bằng
`--asr-decoder result/chunkformer-optimization/decoder.json` trong CLI inference
hoặc `lifemate.experiments`. Artifact chứa LM và tham số beam, được kiểm tra
checksum vocabulary trước khi decode; experiment lưu checksum artifact trong
metadata. Giữ concurrency 1 vì adapter tạm chuyển model sang chế độ xuất logits.
Không dùng label/transcript của sample làm input cho decoder ở runtime.

Benchmark offline: chạy `PYTHONPATH=src .venv/bin/python scripts/benchmark_chunkformer.py`
(sweep 5 configs trên 50 mẫu ngoài validation, baseline và candidate trên 980 audio
của 300 validation samples), tiếp theo `scripts/benchmark_ctc_beam.py` và
`scripts/report_chunkformer_benchmark.py` với cùng `PYTHONPATH=src`.
LM học từ 1.195 mẫu còn lại, loại thêm câu trùng nguyên văn với tune/validation.
Báo cáo: `result/chunkformer-optimization/report.md`. Các lệnh benchmark chỉ chạy
ASR cục bộ; không tạo LangSmith experiment hay chạy agent. Không suy ra điểm
end-to-end hoặc tiêu chí latency 30s từ latency riêng ASR.

### Gipformer 1.5 RNN-T (optional ASR)

Backend `--asr-backend gipformer --asr-model models/gipformer1.5-68M-rnnt`
được hỗ trợ bởi CLI inference, ASR eval và LangSmith experiments. Mặc định dùng
ONNX FP32 / CUDA, modified_beam_search, max_active_paths=4, CPU threads=4;
batch/concurrency vẫn 1. Không dùng CTC `--asr-decoder` với backend RNN-T này.
ASR eval có thể chọn CPU bằng `--device cpu`; inference/experiments hiện dùng CUDA.
Adapter yêu cầu local files, không tự download. Xem `requirements-gipformer.txt`
để cài runtime CUDA từ wheel chính thức; không cần đổi torch/vLLM.

Model snapshot đã tải ở revision
`dd9227dcd8705c13f33bdbe59728d546ab94480f`. Để tải lại:

```python
from huggingface_hub import snapshot_download
snapshot_download(
    'g-group-ai-lab/gipformer1.5-68M-rnnt',
    revision='dd9227dcd8705c13f33bdbe59728d546ab94480f',
    local_dir='models/gipformer1.5-68M-rnnt',
    allow_patterns=['encoder.onnx', 'decoder.onnx', 'joiner.onnx',
                    'tokens.txt', 'README.md', 'config.json'],
)
```

Benchmark ASR riêng (không gọi LLM):
`PYTHONPATH=src .venv/bin/python scripts/benchmark_gipformer.py`, rồi
`scripts/report_gipformer_benchmark.py` với cùng PYTHONPATH. Báo cáo và checksum:
`result/gipformer-1.5-benchmark/`. Dùng cùng 980 audio của validation 300 và cùng
normalizer như ChunkFormer. Benchmark không thay ASR mặc định hoặc tự chạy lại
agent. Model hiện lưu trên disk repo (được gitignore), không nằm trong /dev/shm.

Publish an existing ASR benchmark to a separate LangSmith experiment (no ASR/LLM rerun):

```bash
PYTHONPATH=src .venv/bin/python scripts/upload_asr_experiment.py \
  --benchmark result/gipformer-1.5-benchmark
```

Dataset `lifemate-asr-validation-300-v1` contains one row per query/history utterance,
with readable reference/output transcripts. `fuzzy_token_f1` uses multiset word F1
with NFC, lowercase and punctuation removal, preserving Vietnamese accents.
`fuzzy_pass_0_8` is true when the score is **>= 0.8** and decoding succeeded.
This measures transcript similarity; it does not guarantee correct actions or tool calls.
Cached-upload run latency is not inference latency; use `original_asr_latency_seconds`
in each run metadata. Provenance and original decoder settings are in experiment metadata.
The immutable reference dataset can be reused to compare other ASR benchmarks.

ASR upload defaults to query only: 300 rows for the fixed validation subset.
Use `--scope all` with a separate dataset name only when explicitly evaluating history too.
