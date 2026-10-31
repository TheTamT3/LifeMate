# Trọng tâm 80/20 cho bài toán LifeMate

## Mục tiêu cốt lõi

Đây là bài toán **điều khiển trạng thái ứng dụng bằng tool**, không chỉ là bài toán chatbot. LLM có vai trò hiểu yêu cầu và tạo tool call; điểm số phụ thuộc chủ yếu vào:

1. Tool call đúng.
2. State cuối cùng đúng.
3. `state_hash` khớp với đáp án.

## 20% yếu tố tạo ra phần lớn điểm số

### 1. Chọn đúng tool

Agent phải:

- Chỉ chọn tool có trong `installed_apps` của sample.
- Chọn đúng app và đúng hành động.
- Không gọi tool nếu yêu cầu không cần thao tác.
- Gọi `sys.ask_missing_info` khi thiếu thông tin cần thiết.
- Không tự tạo tên tool ngoài catalog.

### 2. Truyền đúng arguments

Agent phải điền chính xác:

- Các tham số bắt buộc.
- Đúng kiểu dữ liệu, enum và format.
- Đúng ID của contact, event, device, task...
- Đúng nội dung, thời gian, địa điểm và số điện thoại.

Không nên tự đoán ID. Khi cần, agent nên dùng tool đọc/search để lấy ID hợp lệ.

### 3. Tạo đúng state cuối

Tool phải được thực thi qua `ToolEnv`:

```python
env.call(tool_name, arguments)
```

Không chỉ tạo JSON tool call. Nếu không gọi `env.call()`, state sẽ không được cập nhật và `state_hash` có thể sai.

Sau khi thực thi toàn bộ thao tác:

```python
tool_calls = env.get_tool_calls()
state_hash = env.get_state_hash()
```

Đây là hai trường cần ghi vào `submission.jsonl`.

## Cơ chế chấm điểm cần ghi nhớ

Mỗi sample được đánh giá trên hai mặt:

1. State cuối cùng có đúng không.
2. Tool calls có giống gold calls không.

### State match

`state_hash` phải khớp chính xác với gold `state_hash`. Nếu không khớp, sample bị điểm 0 ở phần state.

Hash phải được lấy từ:

```python
env.get_state_hash()
```

Không tự tính hash và không tự sửa `state.json`.

### Tool-call match

Một call được xem là khớp khi:

- Tên tool giống nhau.
- Mọi argument không fuzzy giống nhau.
- Argument fuzzy có token-F1 lớn hơn `0.6`.

Mỗi call chỉ được ghép với tối đa một gold call. Call bị lỗi schema vẫn được ghi nhận là call không khớp.

### Sample không cần tool

Nếu gold list là `[]`, agent cũng phải trả về:

```json
"tool_calls": []
```

Gọi thêm bất kỳ tool nào trong trường hợp này đều làm sample bị điểm 0.

### Thứ tự gọi tool

Thứ tự không được dùng trực tiếp để ghép tool calls trong metric matching. Tuy nhiên, thứ tự vẫn có thể ảnh hưởng state cuối nếu các thao tác phụ thuộc nhau. Vì vậy, nên gọi theo thứ tự logic và không gọi thử dư thừa.

### Precision và recall

- Precision giảm khi agent gọi thừa hoặc gọi sai tool.
- Recall giảm khi agent bỏ sót gold call.
- Mục tiêu là vừa gọi đủ, vừa không gọi dư.

Do đó, chiến lược an toàn là: chỉ gọi tool khi có đủ bằng chứng từ yêu cầu, context, history và catalog.

## Thứ tự ưu tiên triển khai

| Ưu tiên | Thành phần | Mục tiêu |
|---:|---|---|
| 1 | Tool selection | Chọn đúng tool |
| 2 | Argument extraction | Điền đúng tham số |
| 3 | State transition | Tạo đúng state cuối |
| 4 | Context/history | Hiểu thời gian, người và địa điểm |
| 5 | ASR | Giữ đúng thông tin quan trọng từ audio |
| 6 | Tốc độ và tối ưu model | Tối ưu sau khi độ chính xác ổn định |

## Pipeline nên tập trung

```text
Audio
  → ASR
  → chuẩn hóa transcript
  → lọc tool theo installed_apps
  → LLM tạo tool call có cấu trúc
  → validate schema
  → env.call(...)
  → env.get_state_hash()
  → submission.jsonl
```

## Context cần xử lý chính xác

Agent cần sử dụng:

- `current_time` và `timezone`.
- `location` và `user_profile`.
- `installed_apps`.
- `history` và kết quả tool trước đó.
- Các biểu thức như “mai”, “tối nay”, “tuần sau”.

History đã được áp dụng vào state ban đầu; agent chỉ cần xử lý đúng yêu cầu cuối.

## ASR: đủ tốt theo ý nghĩa, không cần giống từng chữ

ASR là đầu vào, nhưng không phải mục tiêu chấm trực tiếp chính. Cần ưu tiên nhận diện chính xác các trường ảnh hưởng đến tool call:

- Tên người và contact.
- Địa điểm và thiết bị.
- Ngày, giờ, múi giờ.
- Số điện thoại, số lượng và giá trị.
- Nội dung tin nhắn hoặc ghi chú.

Một transcript không giống hoàn toàn reference vẫn có thể đạt điểm nếu agent tạo đúng tool call. Ngược lại, transcript đẹp nhưng sai ID hoặc sai thời gian vẫn làm state sai.

## Chiến lược phát triển theo giai đoạn

### Giai đoạn 1: Baseline xác định tool

- Dùng prompt rõ ràng.
- Lọc catalog theo `installed_apps`.
- Yêu cầu LLM trả structured tool call.
- Chưa cần fine-tune hoặc few-shot.

Mục tiêu: đo riêng tỷ lệ chọn đúng tool và tỷ lệ lỗi schema.

### Giai đoạn 2: Cải thiện arguments

- Thêm quy tắc chuẩn hóa thời gian và số điện thoại.
- Dùng tool đọc/search để lấy ID thay vì đoán.
- Xử lý `x-one-of`, `x-ref` và fuzzy fields.
- Kiểm tra bằng `env.validate()` trước khi thực thi khi phù hợp.

Mục tiêu: giảm lỗi arguments và tăng state match.

### Giai đoạn 3: Xử lý context khó

- History nhiều lượt.
- Yêu cầu thiếu thông tin.
- Multi-step phụ thuộc kết quả tool trước.
- Các mốc thời gian tương đối.

Mục tiêu: xử lý các sample khó sau khi baseline đã ổn định.

### Giai đoạn 4: Tối ưu model và tốc độ

- So sánh model nhỏ/lớn.
- Tối ưu vLLM, batching và cache.
- Quantization chỉ sau khi có baseline độ chính xác.

Không nên tối ưu tốc độ trước khi biết lỗi chính nằm ở ASR, tool selection hay arguments.

## Những việc chưa nên ưu tiên

- Fine-tune model ngay từ đầu.
- Xây multi-agent hoặc memory phức tạp.
- Gọi thử nhiều tool rồi chọn kết quả.
- Đọc trực tiếp `state.json`.
- Tự implement lại `zaic_tools`.
- Tối ưu tốc độ trước khi tool call đúng.
- Dùng tool ngoài catalog hoặc ngoài `installed_apps`.
- Tạo câu trả lời tự nhiên dài; phần text không phải trọng tâm chấm điểm.
- Tối ưu ASR bằng WER/CER mà không kiểm tra tác động đến tool call.

## Tiêu chí kiểm tra một sample

Trước khi xem sample là đúng, cần kiểm tra:

1. Tool có được phép sử dụng không?
2. Tên tool có chính xác không?
3. Arguments có đúng schema và đúng ID không?
4. Có gọi thừa hoặc gọi thiếu tool không?
5. State sau khi chạy có đúng mong muốn không?
6. `state_hash` có được lấy bằng `env.get_state_hash()` không?

## Cách phân tích lỗi theo 80/20

Khi một sample thất bại, phân loại lỗi vào đúng một nhóm trước khi sửa:

1. **ASR lỗi**: transcript sai tên, thời gian, số hoặc nội dung.
2. **Ý định lỗi**: chọn sai app hoặc sai tool.
3. **Argument lỗi**: thiếu, sai kiểu, sai enum hoặc sai ID.
4. **Execution lỗi**: gọi sai thứ tự hoặc thao tác không tạo state mong muốn.
5. **Submission lỗi**: ghi sai `tool_calls` hoặc `state_hash`.

Tập trung sửa nhóm chiếm nhiều lỗi nhất thay vì chỉnh prompt/model một cách dàn trải.

## Kết luận

Hãy tối ưu theo thứ tự:

```text
Đúng tool
  → Đúng arguments
  → Đúng state
  → Đúng state_hash
```

ASR và việc chọn model chỉ nên được tối ưu sau khi pipeline tool calling cơ bản đã ổn định. Một model nhỏ nhưng gọi đúng tool thường có giá trị hơn một model lớn nhưng tạo tool call không chính xác.
