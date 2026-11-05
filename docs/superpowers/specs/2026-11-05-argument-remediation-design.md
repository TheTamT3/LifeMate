# Thiết kế xử lý chín hướng fix còn cần làm rõ

Ngày: 05/11/2026. Trạng thái: dự thảo chờ duyệt thiết kế.

## 1. Mục đích và phạm vi

Giảm lỗi tham số của agent mà không viết quy tắc riêng cho các sample đã thấy, không tự chọn đáp án thay agent và không làm mất những cách gọi hợp lệ. Thiết kế dựa trên [REMEDIATION_RULES.md](../../REMEDIATION_RULES.md).

Người dùng đã chọn **hướng A: thay đổi nhỏ, có căn cứ rõ** trong hội thoại. Việc chọn hướng không có nghĩa đã implement hoặc đã xác nhận hiệu quả. Bản này cụ thể hóa chín mục còn vướng trong [report](../../../review_data/argument_mechanisms_5efb0ae0_20261104/REPORT.md); chưa phải plan sửa toàn bộ 19 giả thuyết.

Hai hướng cũ H-DATE-MEM và H-CLOCK-PARSE đang mang trạng thái không đồng ý trong `solution_review.json`. Các phương án thay thế dưới đây không xóa trạng thái đó. Không sửa file quyết định cũ trong bước thiết kế này.

## 2. Các hướng đã cân nhắc

| Hướng | Nội dung | Đánh đổi | Quyết định |
| --- | --- | --- | --- |
| A | Làm rõ instruction hiện có; code chỉ xử lý quy tắc chắc chắn; điều chưa rõ ghi nhận để điều tra | Ít đổi kiến trúc; vẫn có thể xảy ra lỗi model | Người dùng chọn |
| B | Thêm bước model lập kế hoạch, khai báo fact/nguồn/dependency và pipeline kiểm trước hành động | Phạm vi lớn, có thể chặn nhầm, tăng latency và lượt model | Không chọn cho đợt này |

## 3. Hiện trạng và giới hạn

- `src/lifemate/agent_policy.py` đã có TIME_POLICY và EVIDENCE_POLICY về mốc thời gian, nguồn dữ kiện, literal, thông tin thiếu và mặc định. Sửa các câu liên quan thay vì nối thêm chín đoạn trùng nhau.
- `src/lifemate/pydantic_agent.py` kiểm schema trước `env.call`; hiện chưa có bộ nhớ fact hay registry loại ID. `x-ref` được gửi trong schema, chưa được kiểm về loại đối tượng.
- Tool chạy tuần tự không có nghĩa call sau được model soạn sau khi đã nhận kết quả call trước. Không thay cơ chế thực thi để giải quyết vấn đề này trong đợt A.
- Giữ giới hạn request hiện tại là 10, quyền quyết định tiếp tục/dừng của agent và cơ chế hỏi đang có.
- Không thêm lượt model, dependency, tool ngoài catalog hoặc model phụ. Không sửa catalog/runtime chính thức, label, trace gốc hay dữ liệu review.
- Không bật lại thinking history; không xây parser giờ, bộ nhớ fact, bộ tự sửa literal hoặc bộ nhận diện dependency tổng quát.
- Cập nhật theo review của người dùng: Task 6–8 trong plan chuyển sang backlog điều tra; không triển khai observer nguồn ID, mapping theo tool, hook hoặc metadata chẩn đoán trong đợt fixing. H-ID-ROLE chỉ sửa instruction.
- Người dùng ưu tiên thời gian dưới 30 giây và hiện chưa có tài nguyên replay. Không cam kết latency hoặc chất lượng model sau thay đổi khi chưa đo.

## 4. Nội dung chín mục

Các đoạn trích là nội dung đề xuất để tích hợp vào policy hiện có, không phải chín đoạn phải nối nguyên văn. Builder được chỉnh câu chữ cho gọn nhưng không mở rộng ý nghĩa.

### H-DATE-MEM — giữ ngày đã xác định, chưa thêm bộ nhớ

Thay phương án bộ nhớ fact bằng việc làm rõ TIME_POLICY:

> Giữ ngày được nêu rõ trong yêu cầu còn hiệu lực. Sau tra cứu hoặc thử lại, vẫn đối chiếu ngày với yêu cầu và context; chỉ thay khi có lời sửa hoặc căn cứ mới. Với ngày phải suy ra, kiểm lại theo context thay vì coi một suy luận trước đó là dữ kiện đã xác nhận.

Không trích ngày từ reasoning làm fact bền. Instruction chỉ là phương án giảm drift, chưa xác nhận việc bỏ thinking gây ra lỗi.

### H-CLOCK-PARSE — làm rõ quy đổi giờ, hoãn parser

Làm rõ phần quy đổi trong TIME_POLICY:

> Khi đổi cách nói giờ thành thời điểm dạng số, giữ đủ giờ, phút và buổi; kiểm tra các thành phần cộng/trừ và chuyển ngày nếu có. Chỉ hỏi khi còn cách hiểu khác nhau ảnh hưởng hành động mà context chưa giải quyết được.

Không hỏi mọi câu không ghi sáng/tối; context có thể đủ. Không thêm regex nhận diện ba câu lỗi. Hướng parser cũ tiếp tục hoãn.

### H-ANCHOR-ROLE — phân biệt vai trò mốc trước khi tính

Làm rõ TIME_POLICY:

> Khi có nhiều mốc thời gian, xác định mốc mà yêu cầu đang tham chiếu trước khi tính. Phân biệt thời điểm sự kiện, di chuyển, nhắc và hạn chót; dùng phiên bản mới nhất còn hiệu lực của đúng mốc đó. Không dùng một mốc khác chỉ vì xuất hiện gần hơn trong hội thoại.

Không bắt model xuất một bảng reasoning hoặc thêm lượt phân loại. Không thêm helper cho tới khi có giao diện đầu vào và căn cứ chọn mốc được duyệt riêng.

### H-ID-ROLE — sửa instruction; quan sát nguồn ID chuyển backlog

Làm rõ BASE_POLICY/EVIDENCE_POLICY:

> Dùng ID đúng loại đối tượng mà tham số yêu cầu. ID tìm được cho cùng một người hoặc sự việc không mặc định thay thế cho ID của loại đối tượng khác; dùng nguồn tra cứu phù hợp khi cần.

Đây là hướng fix bằng instruction; chưa có bằng chứng model sẽ hết nhầm ID. Giữ ngoại lệ ID được dùng hợp lệ giữa các app, chẳng hạn ID liên hệ làm contact_id cho tool SMS. Không viết quy tắc cấm ID đi qua app.

Đề xuất code cũ gồm observer nguồn ID, hook pipeline và metadata trace chỉ phục vụ điều tra, không làm thay đổi lựa chọn của agent. Người dùng đã đồng ý chuyển cả ba sang backlog; không tạo registry, mapping theo tool, cờ opt-in, hook hoặc test observer trong đợt này. Nếu cần điều tra riêng sau này thì thiết kế lại trước khi triển khai. Guard chặn/sửa ID vẫn ngoài phạm vi.

### H-MISSING-EXAMPLE — kiểm cách trình bày trước

Giữ quy tắc hiện có rằng ví dụ trong schema không phải dữ kiện. Rà mô tả tool theo ba loại: ví dụ định dạng, default thực tế, enum/giới hạn; không gộp chúng.

Đợt đầu chỉ lập danh sách điểm nhập nhằng có trích nguồn. Không xóa/thay số ví dụ, schema hay description tự động. Nếu có câu nhập nhằng thật, đề xuất semantic note riêng để duyệt; nếu không có, ghi nhận chưa đủ cơ sở cho thay đổi production. Không cần phát minh một fix cho đủ 19 mục.

### H-MISSING-COMMIT — thống nhất nhận định với hành động

Làm rõ EVIDENCE_POLICY, không thêm guard known/unknown:

> Khi chưa xác định được giá trị cần cho hành động, tra cứu nguồn được cấp hoặc hỏi phần thiếu; không đồng thời thực hiện hành động bằng giá trị tự giả định. Giá trị tính được từ dữ kiện đủ căn cứ vẫn được dùng. Những việc độc lập vẫn có thể tiếp tục theo cơ chế hiện có.

Không coi mọi giá trị khác chuỗi trong user input là bịa. Không thay hành vi pause của `sys.ask_missing_info` trong pipeline.

### H-LITERAL-REGEN — giữ chuỗi, hoãn chuẩn hóa tự động

Làm rõ quy tắc literal trong EVIDENCE_POLICY:

> Khi đã xác định chuỗi số, mã hoặc địa chỉ từ nguồn phù hợp, dùng lại chính xác chuỗi đó; giữ số đầu 0, số lặp và đầy đủ ký tự. Không rút ngắn hoặc sửa theo độ dài thường gặp. Nếu cách đọc còn mơ hồ mà context không giải quyết được, hỏi phần chưa rõ.

Không thêm nơi lưu bản sao literal qua lượt hoặc parser số/email ở đợt A. Phân biệt lỗi hiểu từ đầu với lỗi chép lại; không gọi instruction này là fix chung cho cả hai.

### H-CONTENT-DEPEND — chờ kết quả thật trước khi soạn call phụ thuộc

Làm rõ CONDITION_POLICY/EVIDENCE_POLICY:

> Nếu arguments hoặc nội dung của một call cần dữ kiện chỉ có sau kết quả call khác, chờ kết quả đó rồi mới tạo call phụ thuộc. Không bịa dữ kiện hoặc báo thành công trước khi kiểm kết quả. Các call không phụ thuộc nhau vẫn có thể được tạo cùng lượt.

Không hardcode cặp tool, phát hiện dependency bằng keyword hoặc cấm multi-call. Không thêm orchestration mới; instruction không bảo đảm model sẽ tuân thủ và cần ghi rõ giới hạn này.

### H-DEFAULT-AUTHORITY — chính sách mặc định có ngoại lệ ủy quyền

Đề xuất tích hợp vào EVIDENCE_POLICY, thay câu optional hiện tại nếu thiết kế được duyệt:

> Với tham số có mặc định, giữ mặc định khi yêu cầu chưa chỉ định giá trị khác và chưa giao quyền lựa chọn. Khi người dùng đã cho phép lựa chọn, chọn trong phạm vi được giao và theo khả năng tool; không mở rộng quyền đó sang tham số khác.

Không nâng priority chỉ vì có deadline. Chỉ dẫn rõ như ưu tiên cao vẫn được thực hiện; câu “chọn mức ưu tiên phù hợp giúp tôi” cho phép agent chọn mức trong phạm vi đó. Không đồng nhất mọi cách nói gián tiếp như “gấp” với một enum cụ thể nếu chính sách/tool chưa quy định.

Đây là chính sách assistant đề xuất trong hướng A, cần duyệt cùng thiết kế. Không tự xóa priority trong arguments; agent vẫn quyết định giá trị theo instruction.

## 5. Tích hợp và thứ tự

1. Rà policy hiện tại và các đoạn trùng/ngoại lệ; lập diff instruction cho bảy mục có sửa lời hướng dẫn: DATE-MEM, CLOCK-PARSE, ANCHOR-ROLE, ID-ROLE, MISSING-COMMIT, LITERAL-REGEN, CONTENT-DEPEND; DEFAULT-AUTHORITY là mục chính sách thứ tám. MISSING-EXAMPLE chỉ audit.
2. Chia các diff theo nội dung thời gian, bằng chứng/chuỗi/mặc định và phụ thuộc giữa call để review và có thể hoàn tác riêng. Không bắt buộc ghép tất cả thành một prompt release.
3. Không xây chẩn đoán ID trong đợt fixing; giữ Task 6–8 của plan ở backlog điều tra và chỉ xem xét khi có yêu cầu riêng.
4. Không tự gộp mười giả thuyết khác hoặc hướng code từng bị từ chối vào scope này. Plan bao phủ 19 mục sau này có thể tham chiếu thiết kế này.

## 6. Kiểm chứng và tiêu chí chấp nhận

### Có thể kiểm offline

- Review instruction về mâu thuẫn, lặp và ngoại lệ. Test kiểm prompt được dựng đúng chỉ chứng minh wiring, không chứng minh model hiểu.
- Đối chiếu instruction ID với cả lời gọi hợp lệ qua app, trường hợp cùng chuỗi có nhiều vai trò và ID chưa biết nguồn. Không được biến thiếu nguồn thành quy tắc chặn/hỏi chung; không có observer để bật/tắt hoặc kiểm trong đợt này.
- Giữ nguyên schema/tool được cấp, request limit và hành vi pause. Không thêm model request hoặc dependency.
- Chuẩn bị bảng tình huống đánh giá cho từng rule: lỗi đã thấy, đối chứng đang đúng và biến thể chưa dùng khi thiết kế. Bao gồm trường hợp user sửa ngày, context đủ buổi, user cho chọn tùy ý, literal khác độ dài phổ biến và hai call độc lập.
- Không dùng fake-model test để tuyên bố model thật đã hết bịa, hết drift hoặc chọn đúng ID.

### Khi có tài nguyên và được phép replay

So sánh cùng bộ 300 với baseline, theo từng sample và từng cụm thay đổi: cải thiện, regression, không đổi, lỗi thực thi, latency và lượt model. Quan sát nguồn ID và guard không thuộc đợt này. Chưa replay thì ghi rõ “logic offline đã kiểm; chất lượng model và yêu cầu dưới 30 giây chưa xác nhận”.

### Hoàn tác và dữ liệu

Instruction được chia diff theo cụm để hoàn tác riêng. Không ghi đè trace/reference/review cũ; không thêm metadata ID. Không commit/push hoặc sửa report gốc trong phạm vi viết thiết kế này.

## 7. Những lựa chọn để builder quyết định

Builder chọn cấu trúc test theo code hiện tại và tối giản câu chữ sau khi đối chiếu policy; không được thêm observer, mapping ID, metadata, parser, guard chặn hoặc cơ chế memory. Nếu cần đổi các giới hạn này thì quay lại review thiết kế.

## 8. Trạng thái duyệt

- Hướng A: người dùng đã chọn.
- Task 6–8: người dùng đã đồng ý chuyển sang backlog; H-ID-ROLE chỉ còn instruction trong đợt fixing.
- Thiết kế cụ thể và chính sách DEFAULT-AUTHORITY trong tài liệu: chờ người dùng duyệt.
- Code, instruction production và `solution_review.json`: chưa thay đổi trong bước này.
- Sau khi thiết kế được duyệt: tạo implementation plan trước khi triển khai.
