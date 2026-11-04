# LangSmith Full E2E Smoke Trace

## Intent

Mục 8 của runbook cần kiểm tra đúng pipeline thật trên một sample và đồng thời
đẩy trace lên LangSmith để debug. Trace không được thay thế model, ASR hoặc
ToolEnv bằng mock.

## Goals

- Chạy Gipformer ASR thật, Qwen3-4B qua vLLM thật, PydanticAI và ToolEnv thật.
- Ghi một trace gốc có sample id, output tool calls và `state_hash`.
- Ghi child run cho ASR, agent/LLM và từng tool call.
- Giữ `baseline.py` và đường chạy submission hoàn toàn không phụ thuộc LangSmith.

## Non-goals and constraints

- Không dùng script `smoke_langsmith.py` mock hiện tại.
- Không gửi dữ liệu khi chạy competition offline; trace chỉ là lệnh debug opt-in.
- Máy chạy smoke cần LangSmith API key và Internet.

## Chosen approach

Thêm module tracer nhỏ và script CLI riêng. Script khởi tạo các dependency thật,
sau đó bọc các điểm vào hiện có của `runner.run_sample`: `transcript`,
`run_agent` và `ToolEnv.call`. Sau khi chạy xong, root run nhận kết quả cuối.

## Success criteria

Lệnh smoke in ra `run_id`, `tool_calls`, `state_hash`; mở run đó trên LangSmith
thấy child runs cho ASR, agent và từng tool call. Lệnh baseline 300 vẫn chạy khi
không cài LangSmith.
