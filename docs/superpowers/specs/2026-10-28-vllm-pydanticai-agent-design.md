# Thiết kế agent PydanticAI + vLLM

## Mục đích

Thay lớp agent tự viết hiện tại bằng PydanticAI thực sự, nhưng giữ nguyên các
quy tắc đánh giá và an toàn của LifeMate. Checkpoint `Qwen/Qwen3-4B` chạy nội
bộ qua vLLM; PydanticAI giao tiếp với endpoint OpenAI-compatible tại
`localhost`.

Mục tiêu là để framework phụ trách schema tool, kiểm tra tham số, lịch sử gọi
tool và vòng lặp nhiều bước. `ToolEnv` của ban tổ chức vẫn là nơi duy nhất được
phép đọc/ghi dữ liệu app và tạo `state_hash`.

## Mục tiêu cần đạt

- Dùng `PydanticAI Agent` làm lớp điều phối tool calling.
- Dùng `Qwen/Qwen3-4B` chạy hoàn toàn offline qua vLLM OpenAI-compatible.
- Tạo tool động theo `context.installed_apps` và schema trong tools catalog.
- Hỗ trợ chuỗi gọi nhiều bước kiểu đọc rồi ghi, tối đa 8 lượt tool-call cho mỗi
  sample.
- Giữ output cuối cùng đúng ba trường `id`, `tool_calls`, `state_hash`; hai
  trường sau phải lấy từ `ToolEnv`.
- Bảo đảm suy luận có thể tái lập: `temperature=0`, seed cố định và không dùng
  API hoặc model bên ngoài khi inference.

## Ngoài phạm vi thay đổi này

- Chưa fine-tune/LoRA, few-shot, Docker entrypoint hoặc benchmark hiệu năng.
- Không thay ASR, cách lọc tools, định dạng JSONL đầu vào, hay logic tạo state
  hash.
- Không chạy vLLM trên máy Windows có RTX 3050 4 GB; máy đó chỉ dùng để test
  mock. vLLM sẽ chạy trên Colab hoặc server Linux có GPU.

## Ràng buộc

- LLM phải dưới 5B tham số và context không quá 16K; `Qwen/Qwen3-4B` đáp ứng
  giới hạn này.
- Khi thi, toàn bộ inference phải offline. Endpoint chỉ được là local
  (`localhost` hoặc `127.0.0.1`), không chấp nhận URL từ xa.
- Mỗi sample tạo đúng một `ToolEnv`; tuyệt đối không đọc, parse hoặc sao chép
  file trong `<split>_environment/`, bao gồm `state.json`.
- Chỉ tool xuất hiện trong `installed_apps` mới được đăng ký hoặc gọi. Tên,
  mô tả và JSON Schema lấy từ catalog của split tương ứng.
- Mọi `env.call()` phải xuất hiện trong `env.get_tool_calls()` và submission.

## Các hướng đã cân nhắc

1. **Custom Transformers adapter trong cùng process:** ít process hơn nhưng
   phải tự triển khai adapter PydanticAI, chat template, streaming và tool
   protocol.
2. **Hybrid parser:** tiếp tục tự sinh/parse JSON, chỉ dùng Pydantic models.
   Ít rủi ro hơn nhưng không chuyển hẳn sang agent framework.
3. **PydanticAI + vLLM server (đã chọn):** PydanticAI sử dụng OpenAI provider
   có sẵn, còn vLLM tối ưu inference/cache trên Linux GPU. Đổi lại cần một
   process server khởi động trước baseline.

Chọn hướng 3 vì cần dùng PydanticAI thực sự và cần throughput tốt trên
Colab/server Linux. vLLM chỉ chạy tại `localhost`, nên vẫn đáp ứng yêu cầu
offline khi benchmark.

## Kiến trúc

```text
audio -> ASR -> yêu cầu tiếng Việt
                    |
sample context + catalog -> các tool PydanticAI tạo động
                    |
PydanticAI Agent -- OpenAI-compatible localhost --> vLLM --> Qwen3-4B
       |                 (temperature 0, local weights)
       v
tool wrapper -> ToolEnv.call(name, arguments) -> kết quả -> Agent
       |
       +-> ToolEnv.get_tool_calls(), ToolEnv.get_state_hash() -> submission
```

## Thiết kế thành phần

### Ranh giới vLLM

- Một process vLLM riêng được khởi động rõ ràng qua runbook, dùng bản local của
  checkpoint `Qwen/Qwen3-4B` và model alias mặc định `qwen3-4b`.
- Baseline nhận `--llm-base-url`, mặc định `http://127.0.0.1:8000/v1`; cấu hình
  sẽ từ chối URL không phải loopback.
- Baseline không tải weights, không gọi hosted service và không dùng remote API.
  Nếu server local chưa chạy thì báo lỗi rõ ràng.
- Cấu hình vLLM dùng suy luận xác định (`temperature=0`, `top_p=1`), context tối
  đa 16.384 token và dung lượng GPU phù hợp môi trường thực thi.

### PydanticAI agent

- Tạo một `Agent` mới cho mỗi sample vì bộ tool hợp lệ và `ToolEnv` là riêng cho
  sample đó. Model client OpenAI-compatible có thể được tái sử dụng.
- Dependencies của agent chỉ gồm `ToolEnv`, catalog tool đã lọc và bản ghi các
  call đã thực thi; không chứa đường dẫn hay nội dung app state.
- System instructions nêu rõ yêu cầu tiếng Việt, chỉ dùng tool đã đăng ký,
  không bịa ID và không gọi tool khi không có hành động cần thực hiện.
- Mỗi tool đã đăng ký có tên chính thức, mô tả từ catalog và Pydantic argument
  model tạo từ JSON schema. Wrapper kiểm tra đầu vào, gọi
  `env.call(official_name, arguments)`, rồi trả về observation có thể chuyển
  thành JSON cho agent.
- Có thể dùng tên hàm Python nội bộ an toàn, nhưng tool definition và lệnh gọi
  `env.call()` luôn giữ tên chính thức dạng có dấu chấm.
- Với yêu cầu nhiều bước, kết quả tool `read` được đưa lại cho model. Trường
  `kind` trong catalog là nguồn xác định: chỉ tiếp tục khi mọi tool ở lượt trước
  có `kind == "read"`; dừng sau `write`, `meta`, không có call, lỗi hoặc 8 lượt.

### Schema catalog và dữ liệu đưa vào prompt

- Catalog train có root object, property kiểu `string`, `integer`, `number`,
  `boolean`, và array; đồng thời dùng `required`, `enum`, `minimum`,
  `exclusiveMinimum`, `format`, `x-one-of`, `x-ref`, `x-match`.
- Factory kiểm tra các ràng buộc kiểu/required/enum/range chuẩn và giữ nguyên
  các trường catalog trong mô tả tool. Các trường `x-*` hướng dẫn model nhưng
  không được tái hiện bằng cách đọc app state.
- JSON Schema không được hỗ trợ phải làm catalog validation thất bại trong lúc
  phát triển, thay vì âm thầm làm yếu schema.
- Agent chỉ thấy: transcript ASR, `context.current_time`, timezone, location,
  user profile, `history` và định nghĩa các tool hợp lệ. Agent không thấy
  `label`, `tool_results`, `final_state`, file trong environment directory hay
  tool không thuộc `installed_apps`.

### Output và xử lý lỗi

- Sau khi chạy, submission luôn lấy `tool_calls` và `state_hash` từ `ToolEnv`,
  không dựng lại từ model messages hay logic cục bộ.
- Tham số tool không hợp lệ bị chặn trước `ToolEnv`. Model trả lời sai định dạng
  hoặc chọn tool không hợp lệ không được tạo environment call.
- `ToolEnv.call()` là đồng bộ, trả về dictionary JSON và không ném exception cho
  tool/schema failure. Schema rejection có dạng `{ "ok": false, "error": ... }`,
  vẫn được ghi vào call log và không đổi state. Lỗi nghiệp vụ trả về
  `{ "ok": true, "done": false, ... }`.
- Wrapper trả dictionary này thành observation có kích thước giới hạn. Agent chỉ
  được tiếp tục sau tool `read` và trong giới hạn số lượt.

## Các file dự kiến thay đổi

- Thay vai trò raw generation của `src/lifemate/llm.py` bằng model factory
  PydanticAI/vLLM và cấu hình kết nối.
- Thêm factory tool PydanticAI (ưu tiên module mới) để chuyển catalog JSON schema
  thành dynamic tools gắn với dependency `ToolEnv`.
- Đơn giản hóa `src/lifemate/runner.py`: tạo agent/dependencies theo sample rồi
  trả output chính thức của environment.
- Mở rộng `src/lifemate/cli.py`, tests và runbook với tuỳ chọn endpoint/model
  vLLM. Các module ASR giữ nguyên.
- Cập nhật `requirements.txt` với dependency OpenAI provider của PydanticAI.
  vLLM chỉ cài trong môi trường serving Linux/Colab, không thêm làm yêu cầu cho
  Windows local.

## Chiến lược kiểm thử

- Unit test chuyển catalog thành tool, giữ nguyên dotted tool name, kiểm tra
  schema/arguments và chặn URL không phải loopback mà không cần GPU/server.
- Mock PydanticAI model/provider và `ToolEnv` để test: không làm gì, từ chối
  tool không có quyền, một lần ghi, và chuỗi đọc rồi ghi.
- Bổ sung CLI test cho endpoint/model options và giữ nguyên các test submission
  UTF-8 hiện có.
- Khi vLLM/Qwen weights sẵn sàng trên Colab hoặc server Linux, chạy một sample
  train thật và xác nhận mọi call/hash đến từ đúng `ToolEnv`.

## Các quyết định để implementer tự chốt

- Tên API/module PydanticAI chính xác sẽ theo bản đã pin
  (`pydantic-ai==1.16.0`) và được kiểm tra từ package/docs cục bộ khi implement.
- Giá trị `gpu-memory-utilization` của vLLM phụ thuộc môi trường; runbook sẽ có
  giá trị khởi đầu an toàn, không hard-code trong logic agent.
