# Kế hoạch sửa lỗi theo cụm cơ chế

Ngày thống nhất: 03/11/2026.

Nguồn phân tích: [Tổng hợp cơ chế lỗi](ERROR_MECHANISM_SYNTHESIS_20261103.md), gồm 97 mục phân loại từ 12 nhóm đã điều tra, được tổng hợp thành 14 cụm. Kế hoạch này chưa bao phủ các nhóm chưa được điều tra.

## Nguyên tắc thực hiện

- Thực hiện theo từng đợt nhỏ: một cụm chính, có thể kèm cụm liên quan chặt chẽ. Không sửa tất cả trong một lần.
- Mỗi đợt một commit để dễ kiểm tra và rollback. Chỉ commit/push khi người dùng yêu cầu.
- Do hạn chế tài nguyên, bỏ qua replay LLM trước khi fix. Dựa vào bằng chứng code/trace, unit test và simulator để xác minh logic.
- Không suy ra cải thiện accuracy hoặc đạt latency dưới 30 giây từ test logic. Các tác động đến hành vi LLM vẫn cần kiểm chứng khi có tài nguyên.
- Giữ nguyên dữ liệu review, comment, verdict và bằng chứng điều tra; ghi nhận kết quả sửa trong tài liệu riêng.

## Thứ tự các đợt

| Đợt | Cụm | Mục tiêu | Lý do / lưu ý |
|---|---|---|---|
| 1 | R01 — Pipeline dừng sớm | Xử lý điều kiện kết thúc vòng lặp khi còn tác vụ cần xử lý | Làm riêng vì ảnh hưởng các bước phía sau. Không bỏ barrier vô điều kiện; cần kiểm tra giới hạn lượt, hành động lặp và kết quả done=false. |
| 2 | R04 — Điều kiện và nhánh hành động | Giữ đúng điều kiện, nhánh được phép và fallback | Kiểm tra cả điều kiện true/false, không kéo hành động từ nhánh khác và không tự giả định thanh toán một phần. |
| 3 | R05 — Ý định đã sửa hoặc rút | Giữ yêu cầu cuối cùng xuyên suốt các lượt tra cứu | Không thực thi hoặc hỏi tham số cho ý định đã rút; không quay lại kênh cũ khi kênh mới không khả dụng. |
| 4 | R02 + R03 — Chọn tool và grounding thông tin | Chọn đúng nghiệp vụ trước, rồi tra cứu/hỏi dữ liệu cần thiết | Có thể làm chung do liên quan chặt chẽ; tách commit nếu thay đổi lớn. Không tự điền ID hoặc giá trị ví dụ thành dữ kiện của sample. |
| 5a | R06 — Thời gian | Kiểm tra anchor, quy đổi ngày giờ, chuỗi thời gian và hướng dịch chuyển | Kiểm tra riêng bằng logic xác định; format hợp lệ không chứng minh thời gian đúng. |
| 5b | R07 — Bộ lọc và bao phủ truy vấn | Tránh mất bằng chứng hoặc ứng viên do filter | Phân biệt thiếu ID với chuỗi None; không suy kết quả rỗng thành không tồn tại khi truy vấn chưa đủ bao phủ. |
| Sau | R08, R09, C01 | Sửa literal, giá trị vận hành tự thêm và lệch contract/runtime | Làm riêng từng cơ chế theo bằng chứng cụ thể; có thể điều chỉnh ưu tiên nếu phát hiện lỗi rõ, ảnh hưởng lớn. |

Thứ tự trên là thứ tự ưu tiên, không phải cam kết rằng mọi cụm đều cần thay đổi code. Với lỗi model, xác định điểm can thiệp phù hợp trước khi chọn sửa prompt, schema hay guard logic.

## Các cụm không sửa trực tiếp

| Cụm | Cách sử dụng |
|---|---|
| V01 | Giữ làm đối chứng và regression; không mặc định mọi sample liên quan đều đúng toàn bộ. |
| Q01 | Chốt chính sách đánh giá/reference trước khi thay scorer hoặc hành vi agent. |
| X01 | Kết luận hỗn hợp model/pipeline; dùng bằng chứng của các cụm chuyên biệt để xử lý, không tạo thêm một fix chung. |
| X02 | Trạng thái thiếu bằng chứng, ngoài phạm vi hoặc write chưa xảy ra; không coi là root cause độc lập. |

## Quy trình cho mỗi đợt

1. Đọc bằng chứng và sample liên quan trong báo cáo tổng hợp; đối chiếu code hiện tại và kết luận reviewer.
2. Xác định thay đổi nhỏ nhất, hành vi mong muốn và các rủi ro đối với case đang đúng.
3. Sửa và chạy test logic/simulator phù hợp, bao gồm case lỗi cùng case đối chứng. Không cần gọi LLM hoặc chạy lại 300 sample ở bước này.
4. Ghi thay đổi, kết quả kiểm tra, giới hạn chưa xác minh và các sample cần chạy sau này.
5. Hoàn tất đợt hiện tại trước khi sang đợt tiếp theo; lưu commit riêng khi được yêu cầu.

Khi có tài nguyên, chạy một tập nhỏ gồm case lỗi và case đang đúng trước khi chạy lại 300 sample. Theo dõi tool call, state, hành động thừa/lặp, hỏi thừa, số lượt và latency end-to-end dưới 30 giây.

## Mẫu ghi kết quả một đợt

- Đợt / cụm:
- Bằng chứng và sample đại diện:
- Hành vi trước và sau:
- Thay đổi code/prompt/schema:
- Test đã chạy và kết quả:
- Case đối chứng:
- Giới hạn chưa kiểm chứng bằng LLM:
- Sample cần chạy khi có tài nguyên:
- Commit (nếu có):

## Trạng thái ban đầu

Kế hoạch đã được thống nhất. Đợt R01 đã sửa logic và kiểm tra local như ghi bên dưới; chưa xác minh hành vi LLM thực tế.

## Kết quả đợt 1 — R01 · 03/11/2026

- Solution đã được người dùng duyệt: agent quyết định tiếp tục/kết thúc sau write; không dừng vì done=false; chỉ pause khi gọi `sys.ask_missing_info`, không dừng chung mọi meta.
- Đã thay điều kiện dừng `kind != read` trong `run_agent()` bằng kiểm tra tên chính thức `sys.ask_missing_info`. Các tool cùng response vẫn thực thi tuần tự như trước; pause áp dụng sau nhóm tool hiện tại, không hủy những call khác trong cùng response.
- Không thêm chặn write trùng arguments. Agent vẫn có thể thực hiện thao tác lặp; giới hạn request là chốt chặn tài nguyên hiện có, không đảm bảo không lặp.
- Đổi `max_steps` mặc định thành **10 model request** tại RuntimeConfig, VLLMConfig, run_sample và CLI smoke LangSmith; giá trị truyền tường minh vẫn được giữ. Đây là giới hạn request, không phải số tool call hoặc giới hạn 30 giây.
- Phạm vi code: `src/lifemate/pydantic_agent.py`, `config.py`, `vllm.py`, `runner.py`, `scripts/smoke_e2e_langsmith.py`.
- Test regression: tiếp tục sau write, done=false, read/write cùng lượt, meta khác; kết thúc bình thường; giữ các call cùng response và dừng sau hỏi user; chuyển request_limit và ghi lỗi khi giới hạn bị vượt. Test giới hạn dùng exception giả lập, chưa chứng minh enforcement của PydanticAI thật.
- Test trước sửa: 6 fail đúng hành vi cần sửa, 18 pass. Sau sửa: 28 pass trong các file test pydantic_agent/config/vllm/runner; thêm 27 pass cho LangSmith E2E helpers và CLI, tổng 55 pass. Script smoke cũng qua kiểm tra compile.
- Giới hạn kiểm chứng: local PydanticAI không import được do thiếu `opentelemetry._events`; không cài hoặc thay dependency trong đợt này. Test dùng fake agent/tool; chưa chạy tích hợp PydanticAI thật, replay LLM, đo accuracy hoặc latency.
- Các sample kiểm chứng sau khi có tài nguyên: train_0052, train_0672, train_0830 và case đối chứng đã hoàn thành đúng. Theo dõi tác vụ tiếp theo, hỏi user, write lặp/thừa và latency.
- Không sửa prompt, dữ liệu review, reference hoặc nhóm lỗi khác. Chưa commit/push đợt này.
