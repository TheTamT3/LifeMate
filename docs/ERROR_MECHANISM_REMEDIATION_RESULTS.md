# Kết quả xử lý cụm cơ chế lỗi

Ngày cập nhật: 2026-11-03

Phạm vi: 13 cụm còn lại trong `ERROR_MECHANISM_SYNTHESIS_20261103.md`; R01/P01 không được sửa lại.

`code_verified` nghĩa là contract hoặc thay đổi code đã được kiểm tra offline. `instruction_wired` nghĩa là policy đã được nối vào agent và kiểm tra nội dung/wiring; chưa chứng minh model sẽ tuân theo. `policy_unresolved` và `evidence_unresolved` giữ nguyên các câu hỏi chưa thể chốt nếu không có quyết định chính sách hoặc bằng chứng bổ sung. Không replay LLM và không sửa runtime BTC, schema catalog, label, reference, scorer hay dữ liệu review.

| Cụm | Can thiệp | Đã kiểm tra offline | Chưa xác minh / giới hạn | Trạng thái |
|---|---|---|---|---|
| C01 | Ghi rõ `food_delivery.order_history` hiện bỏ qua `limit`; giữ nguyên schema và payload. | Characterization với 3 đơn: `limit=1` và bỏ `limit` trả cùng toàn bộ danh sách. | Agent có diễn giải đúng giới hạn khi chạy model thật hay không. | `code_verified` |
| R02 | Bổ sung semantics đã xác minh cho autopay, báo giá, cập nhật event; policy yêu cầu chọn tool theo nguồn và tác dụng. | Ghi chú chỉ gắn đúng official tool name; test không đổi schema/payload. | Khả năng chọn đúng workflow cần replay. | `instruction_wired` |
| R03 | Policy yêu cầu grounding theo yêu cầu/context/history/kết quả đã xác nhận, tra cứu khi phù hợp và hỏi khi còn thiếu hoặc nhiều ứng viên. | Policy wiring; manifest giữ case theo crosswalk. | Chưa replay các lựa chọn ứng viên hoặc giá trị model sinh. | `instruction_wired` |
| R04 | Policy tổng quát về điều kiện, phủ định, phạm vi, thứ tự ưu tiên và nội dung được gửi/lưu. | Policy wiring; history và nội dung user giữ nguyên; manifest bao gồm các case điều kiện. | Fake/test văn bản không chứng minh model đánh giá nhánh đúng. | `instruction_wired` |
| R05 | Policy xác định yêu cầu còn hiệu lực sau lời sửa/rút; không thêm bộ lọc từ khóa hay sửa history. | Policy wiring; history nhiều lượt, tool call/result và request mới nhất được giữ nguyên. | Chưa replay để xác nhận model không phục hồi yêu cầu đã rút. | `instruction_wired` |
| R06 | Tạo facts ngày/thứ 14 ngày từ `context.current_time` có offset; thêm policy về anchor, giờ, hướng dịch chuyển và múi giờ. | Unit test giao tuần/tháng/năm, offset, timestamp thiếu/sai, offset/name mismatch; system prompt không lộ label/state; tool result sau update giữ nguyên làm mốc có thể tham chiếu trong history. | Không giải quyết chọn mốc sự kiện, diễn giải giờ nói, arithmetic phức tạp hoặc cách xử lý xung đột múi giờ; model chưa replay. | `code_verified` + `instruction_wired` |
| R07 | Bổ sung semantics cho `since` là cận dưới và `tracking_id` là exact lookup; policy yêu cầu kiểm tra độ bao phủ truy vấn, không tự bỏ filter. | Contract test giữ omit và literal `"None"`; `since` gồm thời điểm bằng cận dưới; không tự retry/query rộng. | Lựa chọn filter của model cần replay. | `code_verified` + `instruction_wired` |
| R08 | Sửa regex email tối thiểu; policy cấm tự sinh địa chỉ hoặc người nhận. | Test synthetic schema cho thấy literal hợp lệ có `+`/`.` được chấp nhận; whitespace, thiếu domain và nhiều `@` bị từ chối; không tự thêm người nhận. | Catalog train hiện không khai báo `format: email`, nên chưa chứng minh validator này tác động đến tool thật hoặc giải quyết case 0681; cần model replay để đánh giá lời đọc. | `code_verified` + `instruction_wired` |
| R09 | Bổ sung semantics cho nhiệt độ optional và priority mặc định; policy giới hạn tự thêm giá trị. | Bỏ nhiệt độ giữ nhiệt độ hiện tại; nhiệt độ 26 gửi rõ vẫn được giữ; priority omit dùng `normal`, giá trị rõ được giữ. | Nhãn mâu thuẫn với state cần phân tích riêng; model chưa replay. | `code_verified` + `instruction_wired` |
| V01 | Tạo manifest regression theo từng membership, không suy “toàn sample đúng” từ một khác biệt cục bộ. | Manifest giữ đủ 83 sample V01 duy nhất, kiểm tra overlap và scorer vẫn tách tool-call score khỏi state hash. | Đối chứng chỉ áp dụng cho hiện tượng được ghi; không xác nhận mọi hành động trong sample đúng. | `code_verified` |
| Q01 | Giữ nguyên scorer nghiêm ngặt; không tự chốt tie, robot mode, địa chỉ, optional text hoặc cửa sổ thời gian. | Regression xác nhận state hash không thay tool-call score, extra args không bị xem là tương đương. | Tie: chưa có luật chọn khi nhiều ứng viên ngang nhau. Robot mode: còn phải chốt mode đúng theo yêu cầu/state. Địa chỉ: chưa có chuẩn canonical cho tương đương. Optional text: cần quyết định khi nào thêm text có căn cứ là chấp nhận được. Cửa sổ ngày: cần phân biệt phạm vi user yêu cầu với range tiện cho query. Các quyết định này cần người dùng chốt trước khi đổi scorer. | `policy_unresolved` |
| X01 | Gắn finding và bằng chứng riêng theo trace đã lưu; không gán mọi trường hợp vào một nhóm R. | Đủ 22 finding riêng theo evidence hiện có, không thay đổi scorer. | Các trace chưa đủ bằng chứng vẫn giữ nguyên kết luận chưa replay; mapping phản ánh nhận định điều tra đã lưu, không khẳng định nguyên nhân đã được replay xác nhận. | `evidence_unresolved` |
| X02 | Ghi từng sample theo trạng thái, không tạo một fix chung. | Manifest có nội dung riêng cho `train_1178`, `train_1564`, `train_1750`. | 1178: insufficient evidence và bất đồng comment cũ về `available=true`; trace dừng trước reserve. 1564: chuyển thất bại do số dư không đủ, lỗi đơn vị được điều tra; note không được lưu. 1750: ngoài P01, các tool tham chiếu đã chạy. Không suy ra cùng root cause. | `evidence_unresolved` |

### Các quyết định Q01 còn mở theo loại case

| Loại | Case và bằng chứng hiện có | Điều cần chốt |
|---|---|---|
| Hòa giá | `train_1712`: hai báo giá có cùng giá. | Quy tắc phá hòa phải dựa trên yêu cầu/state nào; không mặc định chọn quote đầu tiên. |
| Mode robot | `train_0706`, `train_1060`: mode khác nhau nhưng state sau thực thi được ghi nhận tương đương ở các case này. | Mode nào được chấp nhận theo yêu cầu; tương đương state của một case không chứng minh tương đương toàn cục. |
| Địa chỉ giao hàng | `train_0298`: địa chỉ được lấy từ profile trong khi yêu cầu không nêu địa chỉ. | Có cho phép dùng địa chỉ profile làm mặc định khi đặt hàng hay phải hỏi user. |
| Optional text | `train_0267` và các case note/label: có nội dung thêm ngoài tham số cần cho thao tác. | Khi nào text có căn cứ từ yêu cầu được chấp nhận, và khi nào nó làm lệch reference/call matching. Không bỏ toàn bộ optional fields. |
| Cửa sổ lịch sử | `train_0678`, `train_0692`, `train_1373`: query giới hạn cửa sổ, có khả năng bỏ nội dung còn liên quan. | Chốt độ rộng lịch sử theo yêu cầu và mức nào được xem là đủ bao phủ. |
| Bao phủ/filter | `train_0184`, `train_1122` chia query nhưng vẫn đủ state ở case; `train_1556` dùng filter thiếu căn cứ dù kết quả hiện tại đúng. | Phân biệt hành vi tình cờ trả đúng với filter có căn cứ trước khi coi là tương đương. |

## P01/R01 đã có trước đợt này

Giữ thay đổi local hiện có về quyền tự quyết tiếp tục/kết thúc, pause khi gọi `sys.ask_missing_info`, và mặc định 10 model request. Đợt này không thay đổi lại R01. Kết quả wiring/test ở các lần chạy trước không phải bằng chứng model đã đạt chất lượng hoặc giới hạn latency.

## Bổ sung semantics tool

Các note trong `src/lifemate/tool_semantics.py` đối chiếu với source runtime chuẩn: `food_delivery.order_history`, `bill_payment.schedule_autopay`, `ride_hailing.get_quotes`, `calendar.update_event`, `home_security.list_alerts`, `package_tracking.track`, `smart_home.climate_set`, và `tasks.add`. Với autopay, note chỉ xác nhận công cụ cấu hình tự động thanh toán và không trả hóa đơn hiện tại; không hứa runtime sẽ thực hiện thanh toán tương lai. Note chỉ bổ sung mô tả cho model; catalog gốc và simulator không bị sửa.

## Kiểm thử

Kiểm tra cuối đã chạy: `PYTHONPATH=src python -m pytest tests/test_mechanism_cases.py tests/test_tool_semantics.py tests/test_tool_contracts.py tests/test_time_context.py tests/test_agent_policy.py tests/test_pydantic_agent.py tests/test_history_prompt.py tests/test_runner.py tests/test_agent_evaluation.py tests/test_config.py tests/test_vllm.py tests/test_langsmith_e2e.py tests/test_cli.py -q` — **102 passed**. `git diff --check` không báo whitespace error; Git chỉ cảnh báo một số file đang dùng LF và sẽ đổi sang CRLF khi Git ghi lại trên Windows.

Giới hạn runtime: import trực tiếp PydanticAI trong môi trường này vẫn dừng với `ModuleNotFoundError: opentelemetry._events`. Các test kiểm tra `build_agent` dùng fake; vì vậy wiring được kiểm ở mức code/unit test, chưa khởi chạy engine/model thật. Không replay LLM. Wiring policy không chứng minh hiệu quả dự đoán hoặc latency.
