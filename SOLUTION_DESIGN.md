# Baseline solution design

## Cấu hình đã chốt

- **ASR:** `khanhld/chunkformer-ctc-large-vie`. Model tiếng Việt khoảng 110M tham số, có checkpoint và code public, chạy offline qua package `chunkformer`. Model card báo cáo WER 4.18 trên VIVOS, 6.66 trên Common Voice và 14.09 trên VLSP Task 1. Cần kiểm tra điều kiện license CC BY-NC trước khi đóng gói bản nộp.
- **LLM:** Qwen3-4B, decoding greedy/temperature 0.
- **Framework:** PydanticAI cho orchestration và tool schema.
- **Tool selection:** lọc động theo `context.installed_apps`.
- **Learning strategy:** prompting/few-shot trước, chưa fine-tune.
- **Objective:** tối đa hóa state match và tool-call match; tốc độ là ràng buộc phụ.

## Mục tiêu

Tạo một agent offline nhận yêu cầu tiếng Việt, chọn đúng tool, thực thi qua `ToolEnv`, và xuất `id`, `tool_calls`, `state_hash`.

## Kiến trúc

```text
JSONL + audio
   │
   ├─ audio_text (train) / offline ASR (public/private)
   │
   ├─ sample context + history
   ├─ installed_apps ──► allowlist tool
   └─ tools_catalog ───► schema/description
             │
             ▼
      Qwen3-4B qua PydanticAI (greedy, offline)
             │ JSON tool calls
             ▼
          ToolEnv.call()
             │
             ├─ tool result trả lại LLM cho bước tiếp theo
             ├─ state cập nhật trong memory
             └─ get_tool_calls(), get_state_hash()
```

## Quy tắc baseline

- Không đọc, parse hoặc sửa `*_environment/state.json`.
- Mỗi sample chỉ tạo một `ToolEnv`.
- Chỉ đăng ký tool có trong `context.installed_apps`.
- Schema và mô tả lấy từ `<split>_tools_catalog.json`.
- Tên tool truyền cho `env.call()` phải là tên chính thức, ví dụ `calendar.list_events`.
- LLM trả JSON array; lỗi format được chuyển thành `[]` để không tạo call rác.
- Vòng lặp tối đa 8 bước. Multi-step nghĩa là một yêu cầu có thể cần nhiều call nối tiếp: ví dụ `contacts.search` để lấy `contact_id`, sau đó dùng ID đó cho `sms.send`; kết quả bước trước được đưa lại cho LLM.
- `do_sample=False`, `temperature=0`, seed cố định trong model/runtime để tái lập.

## Chạy thử

Từ thư mục `train+public_test/train+public_test`:

```powershell
python ..\..\baseline.py `
  --root . `
  --split train `
  --model C:\models\local-coder-3b `
  --output ..\..\result\submission.jsonl `
  --limit 1
```

Baseline hiện dùng `audio_text` của train để kiểm thử logic. Khi chạy public/private, cần thay `transcript()` bằng ASR local và không gọi API bên ngoài.

## Giai đoạn cải thiện

1. Thêm ASR tiếng Việt local.
2. Fine-tune/LoRA LLM trên tool calls của train, không dùng private/public để gán nhãn.
3. Thêm validator JSON Schema trước `env.call()`.
4. Thêm bộ nhớ hội thoại và bộ chọn tool theo app để giảm context.
5. Đo riêng state-match, precision/recall tool-call và thời gian mỗi sample.
