# Đánh giá 19 giả thuyết lỗi tham số

Đây là ma trận kiểm chứng theo nghĩa hành vi, không phải label production hay đáp án để chèn vào agent. Các sample trong cột evidence chỉ tham chiếu report. Kiểm offline xác nhận code/prompt wiring; không chứng minh model đã hiểu.

| Giả thuyết | Change type | Lỗi quan sát / sample tham chiếu | Đối chứng hợp lệ | Biến thể chưa dùng khi thiết kế | Tiêu chí chấp nhận theo nghĩa | Bằng chứng offline | Bằng chứng model | Hoãn / giới hạn |
|---|---|---|---|---|---|---|---|---|
| H-DATE-ISO | code tạo lịch | Lệch thứ +1 dù bảng lịch đúng: 0787, 0889, 1750 | Ngày viết trực tiếp trong yêu cầu giữ nguyên | Tuần băng qua năm nhuận và tháng | Tên thứ khớp ngày trong lịch chuẩn; không dịch ngày | Task 1 unit và prompt test | Chưa replay | Cải thiện model chưa xác nhận |
| H-DATE-MEM | instruction | Retry đổi 11/10 thành 08/11: 0701 | Người dùng sửa ngày phải dùng ngày mới | Retry không có sửa yêu cầu nhưng context có ngày khác | Giữ ngày user xác định; ngày mới chỉ theo sửa đổi/căn cứ mới | Chưa kiểm | Chưa replay | Fact memory và giữ thinking bị hoãn; hướng cũ disagreed |
| H-CLOCK-PARSE | instruction | Bỏ “rưỡi”/sai “kém”: 0103, 0827, 0168 | “6:30 sáng” và “6 rưỡi” cùng nghĩa khi buổi rõ | “6 rưỡi” có context cho biết buổi hoặc thực sự mơ hồ | Giữ giờ, phút, buổi; chỉ hỏi nếu cách hiểu còn khác và ảnh hưởng hành động | Chưa kiểm | Chưa replay | Parser tự động bị hoãn; hướng cũ disagreed |
| H-ANCHOR-ROLE | instruction | Tính từ lịch/giờ sai vai trò: 0124, 0377, 1449 | Một mốc duy nhất được dùng đúng | Mốc cũ/mới cùng xuất hiện, mốc mới sửa mốc cũ | Tính từ đúng sự kiện và phiên bản còn hiệu lực | Chưa kiểm | Chưa replay | Không code tự chọn mốc |
| H-ANCHOR-MARGIN | instruction | Tự nhắc sớm/đổi hạn: 1201, 0673 | User yêu cầu nhắc trước 10 phút thì trừ đúng 10 phút | Giờ kết thúc chính xác, deadline, user ủy quyền chọn giờ sớm | Không thêm buffer khi chưa được yêu cầu; giữ quyền user giao rõ | Chưa kiểm | Chưa replay | Không guard sửa giờ |
| H-ID-ROLE | instruction | ID loại khác dùng cho beneficiary/chat: 0032, 1221 | Contact ID dùng ở `sms.send.contact_id` theo contract | Cùng ID có nhiều vai trò hợp lệ hoặc ID nguồn chưa biết | Dùng đúng loại ID/nguồn; không cấm dùng ID qua app khi contract cho phép | Chưa kiểm | Chưa replay | Observer Tasks 6–8 chuyển backlog; không guard |
| H-ID-OPTIONAL | semantic note | Cho rằng `get_ride` bắt buộc ID: 1085 | Có ride_id thì tra chính xác chuyến đó | Không ID trả chuyến hiện tại nhưng không khớp giờ user nêu | Model hiểu lookup không ID, vẫn đối chiếu trước khi hủy | Chưa kiểm | Chưa replay | Không tự hủy chuyến hiện tại |
| H-AMBIG-ORDER | instruction | Chọn ứng viên đầu danh sách: 0336, 0350, 0444, 0605, 1585, 1595 | User cho phép chọn tùy ý hoặc có một kết quả khớp duy nhất | Đảo thứ tự nhưng giữ nguyên thuộc tính; hai ứng viên vẫn mơ hồ | Không đổi lựa chọn chỉ theo thứ tự; hỏi khi chưa đủ căn cứ và chưa được giao quyền | Chưa kiểm | Chưa replay | Không code chọn ứng viên |
| H-MISSING-EXAMPLE | audit trước | Chọn số ví dụ volume 2: 1715 | User nói rõ mức 2 | Mô tả gồm ví dụ, default và enum ở cùng trường | Không nhầm ví dụ với dữ kiện/default; chỉ sửa mô tả nếu chứng minh nhập nhằng | Audit Task 9 chưa chạy | Chưa replay | Không tự xóa ví dụ |
| H-MISSING-COMMIT | instruction | Tự giả định amount: 0071, 0191 | Amount có thể tính rõ từ dữ kiện được cấp | Amount thiếu nhưng một việc độc lập vẫn làm được | Không phát hành động cần amount bằng số tự giả; việc độc lập được tiếp tục | Chưa kiểm | Chưa replay | Không guard known/unknown |
| H-LITERAL-REGEN | instruction | Rút mất số cuối qua lượt: 0676; giải mã sai: 0541, 1118 | Chuỗi có số 0 đầu hoặc độ dài khác thường vẫn giữ nguyên | Số lặp, mã/email được user đánh vần, chuỗi mơ hồ | Giữ literal đã xác định; không ép độ dài hay tự sửa dữ liệu mơ hồ | Chưa kiểm | Chưa replay | Không parser hoặc auto-repair |
| H-DIMENSION-SLOT | instruction | Nhầm chiều dài/quantity/giá: 0610, 1039, 1564 | Đại lượng cùng đơn vị và quantity bằng số món | Chuyển cm↔m, giá mua/bán và số lượng khác nhau | Đúng vai trò và đơn vị của mỗi số trước khi tính/điền | Chưa kiểm | Chưa replay | Không guard theo ngưỡng tùy ý |
| H-ENTITY-ATTRIBUTE | instruction | Bỏ qua tên/đặc điểm nhận diện: 1343, 0692 | Tên và thuộc tính đều cùng chỉ một đối tượng | Tên gần giống, giờ/quan hệ phân biệt đối tượng | Giữ mọi thuộc tính nhận diện được user nêu; hỏi nếu xung đột chưa giải được | Chưa kiểm | Chưa replay | Không fuzzy matching |
| H-CONSTRAINT-CONTRACT | semantic note | Thử partial bill payment: 0107 | Ewallet đủ thanh toán toàn bộ thì dùng được | Thiếu số dư nhưng user có/không cho phép nguồn dự phòng | Không gửi amount chia phần; chỉ đổi nguồn khi được phép | Chưa kiểm | Chưa replay | Không sửa arguments/chuyển nguồn; không giải thích 1121/0934 |
| H-ENCODE-BOUNDARY | audit trước | Reasoning car4, client arguments car7: 0111 | Payload raw và parsed giống nhau | Có thể so sánh cùng request trước/sau parser nếu log tồn tại | Chỉ quy generation/parser khi có payload cùng request ở cả hai biên | Audit Task 9 chưa chạy | Chưa replay | Không sửa parser/model khi thiếu raw evidence |
| H-CONTENT-DEPEND | instruction | Bịa mã khi soạn SMS cùng lượt transfer: 0830 | Hai call không phụ thuộc vẫn có thể cùng lượt | Call phụ thuộc thật; tool trả done=false hoặc lỗi | Chỉ soạn dữ kiện phụ thuộc sau return; không cấm call độc lập | Chưa kiểm | Chưa replay | Không dependency engine/hardcode cặp tool |
| H-CONTENT-REWRITE | instruction | Sai tên/ngày/nhầm giờ nội dung: 1484, 1464, 0621 | Paraphrase giữ cùng fact nhưng câu chữ khác | Thay người nhận hoặc ngày giữa lịch sử và body | Fact đã xác nhận không đổi; diễn đạt tương đương vẫn hợp lệ | Chưa kiểm | Chưa replay | Không so body với reference nguyên văn |
| H-DEFAULT-AUTHORITY | policy | Tự nâng priority theo deadline: 0643 | User chỉ định high hoặc giao quyền chọn | User nói gấp/đặt deadline nhưng không nêu priority | Giữ default khi chưa chỉ định/ủy quyền; lựa chọn trong đúng phạm vi đã giao | Chưa kiểm | Chưa replay | Policy cần review; không code bỏ trường |
| H-INTERVAL-SEMANTICS | semantic note | Chỉ đổi start, end cũ còn: 0707 | Chỉ đổi title thì không đổi giờ | Giữ duration khi dời lịch, qua nửa đêm | Note mô tả đúng partial update; model truyền end khi yêu cầu giữ duration và biết lịch cũ | Chưa kiểm | Chưa replay | Không guard hoặc tự đặt end=start+1h |

## Trạng thái sau implement

| Nhóm | Kết quả offline | Kết quả model |
|---|---|---|
| H-DATE-ISO | Lịch đổi sang tên thứ tiếng Việt; unit test và kiểm tra prompt/boundary chạy trong suite liên quan | Chưa replay; chỉ xác nhận phép tạo lịch, chưa xác nhận model hiểu ngày tốt hơn |
| H-DATE-MEM, H-CLOCK-PARSE, H-ANCHOR-ROLE, H-ANCHOR-MARGIN | TIME_POLICY đã được cập nhật; policy/prompt wiring có test | Chưa replay |
| H-ID-ROLE, H-AMBIG-ORDER, H-MISSING-COMMIT, H-LITERAL-REGEN, H-DIMENSION-SLOT, H-ENTITY-ATTRIBUTE, H-CONTENT-REWRITE, H-DEFAULT-AUTHORITY | EVIDENCE_POLICY đã được cập nhật; policy wiring có test | Chưa replay |
| H-CONTENT-DEPEND | CONDITION_POLICY phân biệt call phụ thuộc và độc lập; policy/agent regression tests chạy | Chưa replay; test không chứng minh model tuân thủ thứ tự |
| H-ID-OPTIONAL, H-CONSTRAINT-CONTRACT, H-INTERVAL-SEMANTICS | Semantic notes được thêm; test xác nhận tool description đổi nhưng catalog/schema/arguments/result/runtime call không bị sửa | Chưa replay |
| H-MISSING-EXAMPLE, H-ENCODE-BOUNDARY | Audit artifact và giới hạn bằng chứng được ghi trong [audit](ARGUMENT_REMEDIATION_AUDIT.md) | Chưa replay; chưa có đủ bằng chứng để sửa production |

Không có mục nào được đánh dấu **model fix confirmed**. Test kiểm tra code/prompt wiring và contract; chúng không thay thế replay với model.

H-MISSING-EXAMPLE có một trace cho thấy model viện dẫn ví dụ `2`, nhưng audit chưa kết luận mô tả schema là nguyên nhân tổng quát. H-ENCODE-BOUNDARY thiếu raw generation trước parser nên chưa phân biệt được lỗi do model sinh hay parser chuyển đổi.

Task 6–8 về quan sát nguồn ID vẫn ở backlog theo quyết định trước đó; không phải fix và không được tính đã triển khai. H-DATE-MEM và H-CLOCK-PARSE dùng hướng instruction đã cập nhật; không đưa trở lại phương án memory/parser đã bị từ chối.
