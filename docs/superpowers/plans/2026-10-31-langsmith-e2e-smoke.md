# LangSmith Full E2E Smoke Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thêm lệnh smoke chạy full pipeline thật trên một sample và gửi trace phân cấp lên LangSmith.

**Architecture:** Một module tracer dùng `langsmith.Client` tạo root/child runs. CLI khởi tạo ASR, model vLLM và ToolEnv thật, rồi bọc ba điểm vào của runner mà không sửa đường chạy submission.

**Tech Stack:** Python, LangSmith Client, Gipformer/sherpa-onnx, PydanticAI, vLLM OpenAI-compatible.

**Spec:** `docs/superpowers/specs/2026-10-31-langsmith-e2e-smoke-design.md`

## Global Constraints

- Smoke trace là opt-in và cần Internet cùng `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT`.
- Không mock ASR, LLM hoặc ToolEnv.
- Không đọc trực tiếp `state.json`; state chỉ lấy từ `ToolEnv`.
- Không thay đổi output contract của `baseline.py`.

## Review Focus

- Thiếu biến môi trường phải báo lỗi rõ ràng.
- Tool exception phải được ghi vào child run rồi vẫn được raise.
- Luôn restore monkeypatch khi pipeline lỗi.
- Sample không tồn tại phải dừng trước khi khởi tạo model nặng.
- `state_hash` phải lấy sau toàn bộ tool calls.

### Task 1: Tracing primitives

**Files:**
- Create: `src/lifemate/langsmith_e2e.py`
- Test: `tests/test_langsmith_e2e.py`

- [ ] Viết test cho wrapper ToolEnv ghi inputs/outputs và propagate exception.
- [ ] Chạy test để xác nhận fail vì module chưa có.
- [ ] Implement `LangSmithE2ETracer` và `TracingToolEnv` với Client injection.
- [ ] Chạy test và xác nhận pass.

### Task 2: Real E2E smoke CLI

**Files:**
- Create: `scripts/smoke_e2e_langsmith.py`
- Create: `requirements-langsmith.txt`
- Test: `tests/test_langsmith_e2e.py`

- [ ] Viết test kiểm tra thiếu env và sample id không tồn tại.
- [ ] Chạy test fail.
- [ ] Implement CLI khởi tạo Gipformer, vLLM, ToolEnv thật; bọc ASR/agent/tool và cập nhật root run.
- [ ] Chạy targeted tests pass.

### Task 3: Runbook update

**Files:**
- Modify: `docs/SERVER_E2E_VALIDATION_300_GIPFORMER.md`

- [ ] Thay mục 8 bằng lệnh full E2E trace, bỏ mô tả mock khỏi bước smoke.
- [ ] Giữ ghi chú rõ rằng `baseline.py` không gửi trace.
- [ ] Kiểm tra các lệnh và đường dẫn khớp CLI mới.

### Task 4: Verification

- [ ] Chạy targeted pytest.
- [ ] Chạy compile check cho module/script.
- [ ] Kiểm tra git diff và ghi nhận các test ngoài phạm vi nếu full suite vẫn lỗi do module experimental chưa tracked.
