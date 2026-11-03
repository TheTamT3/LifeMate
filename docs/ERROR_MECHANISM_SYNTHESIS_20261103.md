# Tổng hợp cơ chế từ 12 nhóm đã điều tra · 03/11/2026

97 bucket được ánh xạ đầy đủ vào 14 cụm tổng hợp; 192 sample duy nhất. Đây không phải 14 root cause đã xác nhận. Phạm vi chỉ gồm 12 nhóm đã điều tra; chưa phân tích thêm 34 nhóm còn lại. Không replay, không sửa pipeline, không thay review/comment/phân loại/UI.

9 cụm R là cơ chế lỗi cần kiểm chứng; C01 là lệch contract/runtime có bằng chứng code. V01 là đối chứng, Q01 là chính sách, X01 là bucket hỗn hợp, X02 là trạng thái kết luận. Một sample có thể thuộc nhiều cụm; số sample là mức liên quan, không phải số case sẽ sửa được. P0/P1 là ưu tiên xác minh, không khẳng định tỷ lệ cải thiện.

Nguồn: group_causes.json, P01/prepared.json và investigations hiện hành trong SQLite. evidence.json giữ nguyên bằng chứng/replay/revision hiện tại để đọc từng sample; mechanisms.json chứa crosswalk toàn bộ bucket và sample_map. Báo cáo cũ theo nhóm vẫn là nguồn điều tra chi tiết.

| Cụm | Cơ chế / loại kết luận | Bucket | Sample duy nhất | Ưu tiên |
|---|---|---:|---:|---|
| R01 | Pipeline kết thúc khi còn tác vụ chưa xử lý | 1 | 21 | P0 |
| R02 | Chọn sai nghiệp vụ, nguồn hoặc hiểu sai tác dụng tool | 17 | 19 | P1 |
| R03 | Tự chọn ứng viên hoặc điền dữ liệu thiếu căn cứ | 14 | 29 | P1 |
| R04 | Không giữ điều kiện và nhánh hành động | 12 | 19 | P1 |
| R05 | Mất ý định cuối cùng sau lời sửa hoặc rút yêu cầu | 8 | 8 | P1 |
| R06 | Quy đổi sai mốc, chuỗi hoặc hướng thời gian | 8 | 21 | P1 |
| R07 | Truy vấn làm mất bằng chứng hoặc ứng viên | 6 | 7 | P1 |
| R08 | Giải mã sai literal trong lời nói | 1 | 1 | P2 |
| R09 | Tự thêm giá trị vận hành hoặc metadata mâu thuẫn | 3 | 3 | P1 |
| V01 | Khác biệt hợp lệ hoặc tương đương trong phạm vi bằng chứng | 12 | 83 | P3 |
| Q01 | Tương đương phụ thuộc state hoặc cần chốt chính sách | 10 | 33 | P2 |
| C01 | Contract tham số không được runtime thực hiện | 1 | 2 | P2 |
| X01 | Lỗi đầu tiên do model nhưng chưa tách hết pipeline | 1 | 22 | P2 |
| X02 | Trạng thái thiếu bằng chứng, loại phạm vi hoặc write chưa xảy ra | 3 | 3 | P3 |

## Kế hoạch xác minh

1. R01: dùng ba case 0052, 0672, 0830 đã chọn, khi có server. Giữ nguyên input/model/seed nếu hỗ trợ; chỉ đổi stop policy trong simulator.
2. R04 và R05: kiểm tra hành động không được phép trước; thêm control nhánh true/false và ý định có/không bị rút.
3. R02/R03/R06/R07: kiểm tra riêng công cụ, grounding, thời gian và bao phủ truy vấn; không thay nhiều cơ chế trong cùng phép thử.
4. Q01/V01: thống nhất cách chấm trước khi đổi scorer; dùng các case đúng làm regression.
5. Sau replay mới chọn fix cụ thể và chạy tập lỗi + control. Theo dõi tool/state, hành động thừa, hỏi thừa, số lượt và latency <30s. Không suy ra hiệu quả từ reasoning hoặc số lượng bucket.

## R01 · Pipeline kết thúc khi còn tác vụ chưa xử lý

Loại: `co_che_tinh`. Ưu tiên: P0. Replay 0052, 0672, 0830; so sánh barrier hiện tại với tiếp tục có giới hạn. Kiểm tra hỏi thiếu thông tin, write lặp và done=false; không bỏ barrier vô điều kiện.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| P01:pipeline | Nghi pipeline dừng sớm | train_0052, train_0071, train_0103, train_0191, train_0214, train_0539, train_0672, train_0707, train_0794, train_0811, train_0827, train_0830, train_0840, train_0955, train_0984, train_1011, train_1044, train_1123, train_1158, train_1200, train_1595 |

## R02 · Chọn sai nghiệp vụ, nguồn hoặc hiểu sai tác dụng tool

Loại: `gia_thuyet`. Ưu tiên: P1. Đối chiếu intent với tiền/hậu điều kiện của tool; phân biệt read, cấu hình và thực thi. Replay 0088, 0817, 1141; riêng 0111 cần tách ảnh hưởng pipeline.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M06:bill_transfer | Nhầm thanh toán hóa đơn với chuyển khoản cho người | train_0074, train_0141, train_0361, train_1610 |
| M06:autopay_pay | Nhầm bật autopay với trả hóa đơn hiện tại | train_0088 |
| M06:reminder_alarm | Nhầm nhắc việc có nội dung với báo thức | train_0162, train_0336 |
| M06:reminder_medication | Nhầm nhắc một lần với lịch thuốc lặp | train_0247 |
| M06:quote_booking | Mới lấy báo giá, chưa có thao tác đặt xe | train_0111 |
| M06:beneficiary_contact | Tra người thụ hưởng ngân hàng qua danh bạ điện thoại | train_0362 |
| M06:restore_cancelled | Tưởng update thời gian khôi phục sự kiện đã hủy | train_0817 |
| M06:meeting_source | Tra lịch thường thay nguồn cuộc họp online | train_1011 |
| M06:points_vouchers | Nhầm điểm/reward có thể đổi với voucher đã sở hữu | train_1110, train_1141 |
| M06:checkin_search | Nhầm check-in vé đã đặt với tìm và mua vé mới | train_1113 |
| M06:balance_expense | Nhầm số dư tài khoản với khoản chi điện tháng này | train_1216 |
| M06:recipe_menu | Nhầm danh sách quán/thực đơn với công thức nấu ăn | train_1638 |
| M06:call_sms | Đổi cuộc gọi thành tin nhắn SMS | train_0423 |
| M03:wrong_workflow | Chọn sai workflow rồi tự lấp thông tin của workflow đó | train_0247, train_1113 |
| M02:wrong_api | Sai API trước, rồi tự chọn người nhận chuyển khoản | train_0074 |
| M14:wrong_quantity | Hiểu sai đại lượng điều kiện nên bỏ nguồn kiểm tra | train_1295 |
| M05:wrong_measure | Dùng sai đại lượng và đảo điều kiện sau khi đọc | train_1216 |

## R03 · Tự chọn ứng viên hoặc điền dữ liệu thiếu căn cứ

Loại: `gia_thuyet`. Ưu tiên: P1. Tra cứu nguồn thích hợp trước; lưu nguồn của giá trị; hỏi khi còn thiếu hoặc nhiều ứng viên. Thử 0116, 1292, 1449; kiểm tra cả case đủ dữ liệu để tránh hỏi thừa.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M02:relation | Tự chọn người theo quan hệ hoặc mức độ quen biết suy đoán | train_0025, train_0265, train_0350, train_0414, train_0423, train_0444, train_1585 |
| M02:first | Tự chọn người đầu tiên khi cùng tên | train_0245 |
| M02:chat | Tự gán người vào chat khi chưa có liên kết xác nhận | train_0605, train_1386 |
| M02:preference | Tự đặt tiêu chí hủy: giá cao hoặc đơn mới nhất | train_1010, train_1499 |
| M02:history | Chọn một khả năng trong history còn mơ hồ | train_1292, train_1437, train_1537, train_1605 |
| M02:placeholder | Dùng giá trị other thay thông tin chưa xác định | train_1169 |
| M03:invent_time | Biết thiếu giờ nhưng tự chọn thời điểm hợp lý | train_0116, train_0353 |
| M03:skip_lookup | Đoán giá trị có thể lấy từ công cụ tra cứu | train_0298, train_1533 |
| M03:invent_id | Sinh ID trước khi đọc kết quả tra cứu | train_1085, train_1221, train_1494 |
| M03:example_id | Dùng mã ví dụ trong schema làm mã của sample | train_1292 |
| M03:context_mix | Gán dữ liệu từ đối tượng hoặc ngữ cảnh chưa được xác nhận | train_1475, train_1547, train_1605 |
| M03:invent_evidence | Dùng giờ hiện tại thay timestamp bằng chứng bị thiếu | train_0912 |
| M03:enum_unknown | Dùng enum other để che thông tin chưa xác định | train_1169 |
| M03:invent_level | Tự đặt mức số khi user chỉ yêu cầu thay đổi tương đối | train_1715, train_1728 |

## R04 · Không giữ điều kiện và nhánh hành động

Loại: `gia_thuyet`. Ưu tiên: P1. Biểu diễn điều kiện, nguồn kiểm tra, nhánh được phép và fallback. Thử 0190, 0423, 097; kiểm tra điều kiện false không tạo write và không suy diễn thanh toán một phần.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M14:price_as_fact | Hiểu điều kiện giá thành dữ kiện hoặc lệnh vô điều kiện | train_0197, train_0362 |
| M14:weather_omitted | Bỏ kiểm tra mưa trước khi dời lịch hoặc xóa lịch thuốc | train_0402, train_1130 |
| M14:fallback_unchecked | Chọn fallback trước khi kiểm tra lựa chọn ưu tiên | train_0934, train_0988 |
| M14:status_omitted | Bỏ đọc trạng thái hiện tại vì ưu tiên hành động được nhắc tới | train_1078 |
| M14:send_condition | Gửi nguyên điều kiện cho người nhận thay agent tự quyết định | train_1464 |
| M14:message_omitted | Bỏ đọc tin nhắn làm bằng chứng chọn loại buổi tập | train_1531 |
| M05:branch_leak | Nhận đúng nhánh nhưng kéo thêm action từ nhánh khác | train_0074 |
| M05:partial_payment | Hiểu fallback ngân hàng thành trả ví trước rồi bù phần thiếu | train_0107, train_0141 |
| M05:false_still_act | Biết điều kiện false nhưng vẫn thêm hành động | train_0182, train_0423, train_0533 |
| M05:reverse_predicate | Đảo dấu hoặc đảo ý điều kiện loại trừ | train_0190 |
| M05:aggregate_fallback | Không áp dụng fallback theo tổng hai khoản | train_0361, train_0422 |
| M05:history_gate | Bỏ điều kiện đã được xác định trong history | train_1494 |

## R05 · Mất ý định cuối cùng sau lời sửa hoặc rút yêu cầu

Loại: `gia_thuyet`. Ưu tiên: P1. Chốt ý định còn hiệu lực trước tool call, giữ sau read; thiếu kênh mới không phục hồi yêu cầu đã rút. Thử 0957, 1084, 1286; kiểm tra không thực thi và không hỏi tham số cho ý định đã hủy.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M19:revoked_to_plan | Biến ý định bị rút thành kế hoạch vẫn cần ghi | train_0957 |
| M19:cancel_scope | Đọc thôi khỏi thành hủy phần khác thay vì hủy action | train_0974 |
| M19:channel_fallback | Thiếu kênh mới nên quay về kênh hoặc ý định cũ | train_0978, train_0990 |
| M19:correction_lost | Hiểu lời sửa ở lượt đầu nhưng mất khi chọn ID sau read | train_1084 |
| M19:correction_ignored | Coi lời sửa đích thao tác là lời nói ngoài lề | train_1118 |
| M19:unneeded_meta | Tiếp tục hỏi tham số cho ý định đã rút | train_1192 |
| M19:revoked_grant | Bỏ lời rút yêu cầu và vẫn cấp mã cửa | train_1286 |
| M03:withdrawn | Lấp tham số cho ý định đã bị rút lại | train_0957, train_1286 |

## R06 · Quy đổi sai mốc, chuỗi hoặc hướng thời gian

Loại: `gia_thuyet`. Ưu tiên: P1. Chuẩn hóa anchor/timezone và phép cộng trừ, dùng hàm xác định ngày trước khi write. Thử 0546, 0124, 0381; không dùng kiểm tra format để thay kiểm tra ngữ nghĩa.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M04:weekday | Quy đổi sai thứ trong tuần sang ngày cụ thể | train_0546, train_0610, train_0787, train_0889, train_0988, train_1668 |
| M04:chain | Sai mốc hoặc thiếu khoảng trong chuỗi thời gian | train_0111, train_0908 |
| M04:updated_anchor | Giờ mới đúng nhưng báo thức tính sai mốc hoặc sai phép trừ | train_0124, train_0201 |
| M04:clock | Đọc sai giờ tối hoặc cách nói giờ kém | train_0247, train_1286 |
| M04:direction | Đảo hướng lùi lịch thành sớm hơn | train_0381 |
| M04:missing_anchor | Không lấy giờ sự kiện hoặc chuyến xe làm mốc | train_0033, train_1236 |
| M04:explicit | Tự đổi ngày hoặc deadline đã có căn cứ rõ | train_0673, train_0706, train_1058 |
| M04:relative | Gắn sai mốc hôm nay, ngày kia hoặc hôm sau | train_0975, train_1130, train_1292 |

## R07 · Truy vấn làm mất bằng chứng hoặc ứng viên

Loại: `gia_thuyet`. Ưu tiên: P1. Phân biệt thiếu ID với chuỗi None; kiểm tra semantics filter, mở rộng truy vấn nếu thiếu bao phủ. Thử 0676, 1105, 1449; không mặc định kết quả rỗng đồng nghĩa không tồn tại.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M18:since_now | Dùng since bằng giờ hiện tại làm mất cảnh báo trước đó | train_0676, train_0912 |
| M18:date_window | Tự giới hạn ngày khi user chưa giới hạn thời gian | train_0826, train_1074 |
| M18:location_mismatch | Chuỗi địa điểm không khớp rồi suy ra trạng thái âm | train_0996 |
| M18:null_string | Serialize không có ID thành chuỗi None để lọc | train_1105 |
| M18:candidate_coverage | Tự giới hạn loại thiết bị làm ẩn ứng viên phù hợp | train_1449 |
| M02:coverage | Bộ lọc tự đặt làm mất ứng viên trước khi lựa chọn | train_1449 |

## R08 · Giải mã sai literal trong lời nói

Loại: `gia_thuyet`. Ưu tiên: P2. Kiểm tra tách token email và số người nhận với 0681; đối chiếu text/audio nếu có, không tự thêm địa chỉ.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| M03:spoken_literal | Hiểu sai địa chỉ đọc bằng lời rồi thêm người nhận | train_0681 |

## R09 · Tự thêm giá trị vận hành hoặc metadata mâu thuẫn

Loại: `gia_thuyet`. Ưu tiên: P1. Phân biệt optional với được phép tự chọn; giữ thông số hiện tại/default khi không có yêu cầu. Thử 0643, 1123, 0103; label mâu thuẫn là lỗi hiển thị riêng với state canonical.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| D03:task_priority | Tự nâng priority thay vì giữ mặc định normal | train_0643 |
| D03:device_setting | Tự đặt thông số vận hành ngoài yêu cầu | train_1123 |
| D03:label_conflict | Nhãn báo thức thêm vào còn mâu thuẫn với giờ đã đặt | train_0103 |

## V01 · Khác biệt hợp lệ hoặc tương đương trong phạm vi bằng chứng

Loại: `doi_chung`. Ưu tiên: P3. Giữ làm regression và diễn giải scorer. recovered chỉ chứng minh truy vấn đã phục hồi, không chứng minh toàn sample đúng. date_scope không phải runtime default.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| D02:scope | Lọc đúng phạm vi, giữ dữ liệu cần thiết | train_0017, train_0025, train_0028, train_0032, train_0035, train_0074, train_0110, train_0111, train_0112, train_0141, train_0158, train_0159, train_0201, train_0214, train_0227, train_0233, train_0252, train_0264, train_0294, train_0303, train_0319, train_0326, train_0329, train_0332, train_0349, train_0361, train_0381, train_0402, train_0405, train_0414, train_0437, train_0503, train_0533, train_0534, train_0545, train_0570, train_0597, train_0637, train_0704, train_0811, train_0837, train_0878, train_0943, train_1058, train_1158, train_1349, train_1371, train_1431, train_1585, train_1629 |
| D02:context | Địa điểm lấy từ profile/history hoặc fallback runtime | train_0002, train_0128, train_0154, train_0423, train_0789, train_1330, train_1679 |
| D02:default | Truyền rõ giá trị mặc định hoặc tương đương không lọc | train_0539, train_1044 |
| D02:broad | Mốc lọc rộng hơn yêu cầu, chưa làm sai kết quả | train_0619 |
| D04:repeat | Truyền rõ repeat=once, trùng mặc định | train_0033, train_0097, train_0178, train_0188, train_0294, train_0336, train_0787, train_1295, train_1349, train_1533, train_1568, train_1750 |
| D04:priority | Truyền rõ priority=normal, trùng mặc định | train_0573, train_0610, train_0701, train_0803 |
| D04:timestamp | Thời gian ghi workout trùng current_time mặc định | train_0511, train_0703 |
| D04:calendar_end | Bỏ hoặc truyền end trùng start + 1 giờ | train_0792, train_0829, train_0835, train_1202 |
| D04:route_mode | Truyền rõ phương tiện mặc định của route | train_0437 |
| D04:email_default | unread_only=false tương đương không lọc | train_0539 |
| D04:date_scope | Ngày xổ số là phạm vi truy vấn, không phải mặc định runtime | train_1005, train_1236 |
| M18:recovered | Bộ lọc đầu sai nhưng đã mở rộng và tìm lại đúng dữ liệu | train_1123 |

## Q01 · Tương đương phụ thuộc state hoặc cần chốt chính sách

Loại: `chinh_sach`. Ưu tiên: P2. Chốt riêng phạm vi lịch sử, hòa giá, địa chỉ và optional text. Đọc canonical/scorer; không bỏ mọi optional field. Thử 1712, 0298, 0267 và state robot khác.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| D02:coverage | Chia nhiều truy vấn, đủ state này nhưng có rủi ro bao phủ | train_0184, train_1122 |
| D02:window | Giới hạn cửa sổ đọc: cần xét tin còn giữ và lỗi độc lập | train_0678, train_0692, train_1373 |
| D02:unjustified | Bộ lọc thiếu căn cứ dù kết quả case hiện tại vẫn đúng | train_1556 |
| D04:robot_mode | Mode robot tương đương trong state này, phụ thuộc state | train_0706, train_1060 |
| M02:tie_policy | Hai xe đồng giá: khác reference, cần chốt chính sách hòa giá | train_1712 |
| D03:alarm_label | Tự thêm nhãn báo thức có căn cứ nội dung | train_0028, train_0033, train_0052, train_0162, train_0191, train_0201, train_0381, train_0937, train_1295, train_1349, train_1533, train_1750 |
| D03:transfer_note | Tự thêm note cho giao dịch chuyển tiền | train_0032, train_0110, train_0197, train_0259, train_0267, train_0368, train_0421, train_0422, train_1585 |
| D03:delivery_address | Tự chọn địa chỉ giao hàng từ profile | train_0298 |
| D03:guest_label | Tự thêm nhãn khách cho mã cửa | train_0991 |
| D03:calendar_location | Tự thêm location chung cho sự kiện | train_1202 |

## C01 · Contract tham số không được runtime thực hiện

Loại: `co_che_tinh`. Ưu tiên: P2. Đối chiếu tài liệu/schema với order_history.limit; quyết định triển khai limit hay sửa contract. Kiểm tra 1499, 1547 với dữ liệu dài hơn limit.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| D02:ignored | Tham số limit hợp schema nhưng runtime bỏ qua | train_1499, train_1547 |

## X01 · Lỗi đầu tiên do model nhưng chưa tách hết pipeline

Loại: `tong_hop`. Ưu tiên: P2. Đây là bucket hỗn hợp; không thêm một root cause mới. Dùng kết luận chuyên biệt của các nhóm M và replay ghép cặp trước khi quy trách nhiệm pipeline.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| P01:model | Nghi model, có thể kèm pipeline | train_0107, train_0111, train_0141, train_0162, train_0362, train_0541, train_0704, train_0782, train_0817, train_0937, train_0957, train_0969, train_0974, train_0975, train_1085, train_1369, train_1610, train_1638, train_1648, train_1657, train_1683, train_1697 |

## X02 · Trạng thái thiếu bằng chứng, loại phạm vi hoặc write chưa xảy ra

Loại: `trang_thai`. Ưu tiên: P3. 1178 cần giữ kết luận reviewer; 1750 không thuộc P01; 1564 không suy note đã lưu từ raw write thất bại. Không tính các mục này là nguyên nhân độc lập.

| Mục nguồn | Nhận định nguồn | Sample |
|---|---|---|
| P01:insufficient | Chưa đủ bằng chứng | train_1178 |
| P01:not_p01 | Không thuộc P01 | train_1750 |
| D03:failed_write | Có note trong raw write nhưng giao dịch không thành công | train_1564 |

## Chỉ mục bằng chứng theo sample

Bằng chứng đầy đủ của từng sample nằm trong `review_data/mechanism_synthesis_20261103/evidence.json` (local), gồm kết luận và các block điều tra đã lưu; không coi cụm tổng hợp thay thế phán quyết reviewer.

- `train_0002`: V01
- `train_0017`: V01
- `train_0025`: R03, V01
- `train_0028`: V01, Q01
- `train_0032`: V01, Q01
- `train_0033`: R06, V01, Q01
- `train_0035`: V01
- `train_0052`: R01, Q01
- `train_0071`: R01
- `train_0074`: R02, R04, V01
- `train_0088`: R02
- `train_0097`: V01
- `train_0103`: R01, R09
- `train_0107`: R04, X01
- `train_0110`: V01, Q01
- `train_0111`: R02, R06, V01, X01
- `train_0112`: V01
- `train_0116`: R03
- `train_0124`: R06
- `train_0128`: V01
- `train_0141`: R02, R04, V01, X01
- `train_0154`: V01
- `train_0158`: V01
- `train_0159`: V01
- `train_0162`: R02, Q01, X01
- `train_0178`: V01
- `train_0182`: R04
- `train_0184`: Q01
- `train_0188`: V01
- `train_0190`: R04
- `train_0191`: R01, Q01
- `train_0197`: R04, Q01
- `train_0201`: R06, V01, Q01
- `train_0214`: R01, V01
- `train_0227`: V01
- `train_0233`: V01
- `train_0245`: R03
- `train_0247`: R02, R06
- `train_0252`: V01
- `train_0259`: Q01
- `train_0264`: V01
- `train_0265`: R03
- `train_0267`: Q01
- `train_0294`: V01
- `train_0298`: R03, Q01
- `train_0303`: V01
- `train_0319`: V01
- `train_0326`: V01
- `train_0329`: V01
- `train_0332`: V01
- `train_0336`: R02, V01
- `train_0349`: V01
- `train_0350`: R03
- `train_0353`: R03
- `train_0361`: R02, R04, V01
- `train_0362`: R02, R04, X01
- `train_0368`: Q01
- `train_0381`: R06, V01, Q01
- `train_0402`: R04, V01
- `train_0405`: V01
- `train_0414`: R03, V01
- `train_0421`: Q01
- `train_0422`: R04, Q01
- `train_0423`: R02, R03, R04, V01
- `train_0437`: V01
- `train_0444`: R03
- `train_0503`: V01
- `train_0511`: V01
- `train_0533`: R04, V01
- `train_0534`: V01
- `train_0539`: R01, V01
- `train_0541`: X01
- `train_0545`: V01
- `train_0546`: R06
- `train_0570`: V01
- `train_0573`: V01
- `train_0597`: V01
- `train_0605`: R03
- `train_0610`: R06, V01
- `train_0619`: V01
- `train_0637`: V01
- `train_0643`: R09
- `train_0672`: R01
- `train_0673`: R06
- `train_0676`: R07
- `train_0678`: Q01
- `train_0681`: R08
- `train_0692`: Q01
- `train_0701`: V01
- `train_0703`: V01
- `train_0704`: V01, X01
- `train_0706`: R06, Q01
- `train_0707`: R01
- `train_0782`: X01
- `train_0787`: R06, V01
- `train_0789`: V01
- `train_0792`: V01
- `train_0794`: R01
- `train_0803`: V01
- `train_0811`: R01, V01
- `train_0817`: R02, X01
- `train_0826`: R07
- `train_0827`: R01
- `train_0829`: V01
- `train_0830`: R01
- `train_0835`: V01
- `train_0837`: V01
- `train_0840`: R01
- `train_0878`: V01
- `train_0889`: R06
- `train_0908`: R06
- `train_0912`: R03, R07
- `train_0934`: R04
- `train_0937`: Q01, X01
- `train_0943`: V01
- `train_0955`: R01
- `train_0957`: R05, X01
- `train_0969`: X01
- `train_0974`: R05, X01
- `train_0975`: R06, X01
- `train_0978`: R05
- `train_0984`: R01
- `train_0988`: R04, R06
- `train_0990`: R05
- `train_0991`: Q01
- `train_0996`: R07
- `train_1005`: V01
- `train_1010`: R03
- `train_1011`: R01, R02
- `train_1044`: R01, V01
- `train_1058`: R06, V01
- `train_1060`: Q01
- `train_1074`: R07
- `train_1078`: R04
- `train_1084`: R05
- `train_1085`: R03, X01
- `train_1105`: R07
- `train_1110`: R02
- `train_1113`: R02
- `train_1118`: R05
- `train_1122`: Q01
- `train_1123`: R01, R09, V01
- `train_1130`: R04, R06
- `train_1141`: R02
- `train_1158`: R01, V01
- `train_1169`: R03
- `train_1178`: X02
- `train_1192`: R05
- `train_1200`: R01
- `train_1202`: V01, Q01
- `train_1216`: R02
- `train_1221`: R03
- `train_1236`: R06, V01
- `train_1286`: R05, R06
- `train_1292`: R03, R06
- `train_1295`: R02, V01, Q01
- `train_1330`: V01
- `train_1349`: V01, Q01
- `train_1369`: X01
- `train_1371`: V01
- `train_1373`: Q01
- `train_1386`: R03
- `train_1431`: V01
- `train_1437`: R03
- `train_1449`: R07
- `train_1464`: R04
- `train_1475`: R03
- `train_1494`: R03, R04
- `train_1499`: R03, C01
- `train_1531`: R04
- `train_1533`: R03, V01, Q01
- `train_1537`: R03
- `train_1547`: R03, C01
- `train_1556`: Q01
- `train_1564`: X02
- `train_1568`: V01
- `train_1585`: R03, V01, Q01
- `train_1595`: R01
- `train_1605`: R03
- `train_1610`: R02, X01
- `train_1629`: V01
- `train_1638`: R02, X01
- `train_1648`: X01
- `train_1657`: X01
- `train_1668`: R06
- `train_1679`: V01
- `train_1683`: X01
- `train_1697`: X01
- `train_1712`: Q01
- `train_1715`: R03
- `train_1728`: R03
- `train_1750`: V01, Q01, X02
