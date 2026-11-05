# Bằng chứng contract và hai mục điều tra

Ngày kiểm tra: 05/11/2026. Chỉ dùng catalog/runtime và trace/artifact đã có trong workspace. Không gọi server hoặc LangSmith.

## H-MISSING-EXAMPLE — ví dụ volume 2

| Nguồn | Bằng chứng |
|---|---|
| Trace | `train_1715`, run `9b148cae-c188-4d83-beb8-6a27d39c2fc2`, yêu cầu “nhỏ lại thôi”; call `tv.control(action="volume", volume=2)`. Reasoning nói không biết mức hiện tại nhưng chọn 2; nó dẫn ví dụ “ví dụ 2” trong schema. |
| Catalog | `tv.control.volume`: integer, mô tả “Số nguyên, không dấu chấm hay phẩy, ví dụ 2”. `music.control.volume` có cùng kiểu ví dụ. Đây là ví dụ định dạng, không khai báo default hay mức gợi ý. |
| Runtime | `zaic_tools/apps/tv.py:control` gán trực tiếp `state["volume"] = volume`; không phải thao tác giảm tương đối. Tool `tv.guide` đọc lịch/kênh, không đọc volume. Không thấy tool đọc volume trong catalog TV. |
| Chính sách model hiện tại | EVIDENCE_POLICY nói ví dụ trong schema không phải dữ kiện; tuy vậy reasoning của sample vẫn dùng 2. Một sample hỗ trợ mối liên hệ, không chứng minh đây là nguyên nhân của các case MISSING khác. |

| Trường | Đánh giá |
|---|---|
| Loại giá trị | Ví dụ định dạng số nguyên, không phải default hay enum. |
| Nhập nhằng cần xử lý | Mô tả không nói rõ `volume` là mức tuyệt đối; người dùng nói “nhỏ lại” nhưng tool không nhận lệnh giảm tương đối và không có nguồn để biết mức hiện tại. Đây là giới hạn contract, bên cạnh việc model bắt chước ví dụ. |
| Làm rõ đề xuất để review riêng | Mô tả model-facing có thể ghi: “volume là mức âm lượng tuyệt đối, không phải mức giảm; ví dụ 2 chỉ minh họa định dạng, không phải default/gợi ý. Nếu người dùng chỉ yêu cầu tăng/giảm mà không cho mức cụ thể và không thể đọc mức hiện tại, hỏi mức muốn đặt.” |
| Trạng thái | Chỉ audit; chưa thêm semantic note hay đổi schema/runtime. EVIDENCE_POLICY đã có quy tắc ví dụ không phải dữ kiện, nên chỉ thêm note nếu người dùng duyệt phạm vi làm rõ contract. |
| Đối chứng khi kiểm sau này | “Đặt volume 2” phải giữ 2; “nhỏ lại” không được tự đặt 2; thao tác giảm tương đối không được giả vờ có nếu tool chỉ hỗ trợ mức tuyệt đối. |

## H-ENCODE-BOUNDARY — car4 trong reasoning, car7 trong call

| Ranh giới | Artifact hiện có | Kết luận |
|---|---|---|
| Input/request cùng lượt | Trace experiment v2 lưu prompt, history, schema và request theo model client. | Có ngữ cảnh để đối chiếu yêu cầu car4. |
| Generation thô trước server parser vLLM | Không tìm thấy payload/token generation ở ranh giới này trong local artifacts đã kiểm. | Thiếu bằng chứng. |
| JSON/tool call sau parser vLLM | Trace LangSmith của `train_0111`, run `4572503e-9d95-4038-9466-2c1b9189e393`, ghi structured `ride_hailing.get_quotes` và `ride_hailing.book` với `vehicle="car7"`. Đây là phản hồi đã qua server parser và OpenAI-compatible client. |
| Arguments client trước wrapper local | Evidence trong trace cũng ghi car7 trước wrapper; tool schema cho phép cả car4 và car7. | Chứng minh call đã là car7 ở phía client; không chứng minh model tự sinh car7 trước server parser. |
| So sánh cùng request/call ở hai biên | Không có cặp raw pre-parser và parsed response cùng request ID. | Chưa phân biệt generation với parser. Reasoning nói car4 không thay thế raw generation. |

**Kết luận:** chưa có căn cứ chọn sửa prompt/model hoặc parser. Nếu sau này có server và được phép thu thập, cần log gắn cùng request/call ID gồm raw generation ngay trước parser và structured response ngay sau parser; so sánh hai payload đó. Đến lúc ấy mới đề xuất hướng sửa riêng. Không ép vehicle trong đợt này.

## Giới hạn

- Audit này không chạy model, không tạo tool call và không xác nhận model đã sửa hành vi.
- Mapping contract được trích từ file catalog/runtime hiện có; không thay đổi tool chính thức.
- Trace LangSmith hiện tại đã được parse; không gọi nó là raw generation trước parser.
