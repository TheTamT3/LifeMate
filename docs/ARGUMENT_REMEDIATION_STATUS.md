# Trạng thái xử lý 19 giả thuyết

Ngày cập nhật: 05/11/2026. Đây là kết quả của đợt thực thi theo [implementation plan](superpowers/plans/2026-11-05-argument-hypotheses-remediation.md).

| Task | Phạm vi | Trạng thái thực hiện | Bằng chứng |
|---|---|---|---|
| 1 | H-DATE-ISO | Đã đổi calendar sang `weekday_vi`; biên tháng/năm nhuận được kiểm | `tests/test_time_context.py`, `tests/test_history_prompt.py` |
| 2 | H-DATE-MEM, H-CLOCK-PARSE, H-ANCHOR-ROLE, H-ANCHOR-MARGIN | Đã làm rõ policy thời gian | `tests/test_agent_policy.py`, `tests/test_history_prompt.py`; chỉ kiểm wiring/nội dung policy |
| 3 | H-ID-ROLE, H-AMBIG-ORDER, H-MISSING-COMMIT, H-LITERAL-REGEN, H-DIMENSION-SLOT, H-ENTITY-ATTRIBUTE, H-CONTENT-REWRITE, H-DEFAULT-AUTHORITY | Đã cập nhật EVIDENCE_POLICY | `tests/test_agent_policy.py`; chưa kiểm hành vi model |
| 4 | H-CONTENT-DEPEND | Đã làm rõ call phụ thuộc phải chờ kết quả, call độc lập giữ nguyên | `tests/test_agent_policy.py`, `tests/test_pydantic_agent.py`; chưa kiểm model tuân thủ |
| 5 | H-ID-OPTIONAL, H-CONSTRAINT-CONTRACT, H-INTERVAL-SEMANTICS | Đã bổ sung semantic note theo catalog/runtime | `tests/test_tool_semantics.py`, `tests/test_pydantic_agent.py`; kiểm schema/arguments/result/env call bất biến |
| 6–8 | Chẩn đoán nguồn ID | **Backlog**, theo quyết định người dùng; không implement | Không có observer, mapping, hook hoặc metadata |
| 9 | H-MISSING-EXAMPLE, H-ENCODE-BOUNDARY | Đã kiểm artifact và ghi giới hạn bằng chứng | [audit](ARGUMENT_REMEDIATION_AUDIT.md); chưa sửa production cho hai mục |
| 10 | Kiểm tra tích hợp và bàn giao | Hoàn tất trong phạm vi offline | `94 passed` ở suite liên quan; `compileall` và `git diff --check` sạch; full suite không collect được do 6 lỗi import/dependency |

## Kiểm thử

- Baseline trước sửa: 78 passed ở bảy test module theo lệnh trong plan.
- Task 1: 11 passed (`test_time_context.py`, `test_history_prompt.py`).
- Task 2: 19 passed (`test_agent_policy.py`, `test_history_prompt.py`).
- Task 3: 24 passed (`test_agent_policy.py`, `test_history_prompt.py`, `test_tool_semantics.py`).
- Task 4: 42 passed (`test_agent_policy.py`, `test_pydantic_agent.py`).
- Task 5: 30 passed (`test_tool_semantics.py`, `test_pydantic_agent.py`).
- Suite tích hợp theo plan: 94 passed (`tests/test_time_context.py`, `test_history_prompt.py`, `test_agent_policy.py`, `test_tool_semantics.py`, `test_pydantic_agent.py`, `test_runner.py`, `test_langsmith_e2e.py`, `test_config.py`, `test_vllm.py`, `test_cli.py`).
- `python -m compileall -q src/lifemate`: exit 0.
- `git diff --check`: exit 0; chỉ có cảnh báo Git sẽ đổi LF sang CRLF khi chạm lại các file trên Windows.
- `python -m pytest -q`: không chạy hết suite vì collection dừng ở 6 import lỗi: thiếu `lifemate.asr_eval.ctc_decoder`, `lifemate.experiments`, `lifemate.tracing`, và `opentelemetry._events`. Không có baseline full-suite để quy các lỗi này là trước đó hay do đợt hiện tại.

Các kết quả task kiểm tra chồng lấp test; không cộng chúng thành số test duy nhất.

## Giới hạn và tiếp tục sau này

- Chưa replay model. Không kết luận accuracy tăng, regression bằng 0 hoặc đạt latency dưới 30 giây.
- H-MISSING-EXAMPLE có bằng chứng một sample bắt chước `2`; audit đề xuất làm rõ ý nghĩa absolute volume và ví dụ, đang chờ review riêng trước khi đổi semantic note.
- H-ENCODE-BOUNDARY thiếu dữ liệu generation trước parser vLLM; trace client đã là structured response phía sau parser.
- Task 6–8 chuyển backlog và không được tính là fix.
- Các thay đổi policy/semantic note mới được xác nhận về wiring và tính nguyên vẹn input/schema qua test offline; chưa có replay nên chưa biết model có tuân thủ hay accuracy có tăng.
- Người dùng đã yêu cầu implement, không yêu cầu commit/push. Git metadata read-only trong môi trường hiện tại nên các thay đổi để trong workspace, chưa commit.
