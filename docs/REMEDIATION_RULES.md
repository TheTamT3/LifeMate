# Rules sửa lỗi agent bằng code và instruction

Ngày thống nhất: 05/11/2026.

Áp dụng khi phân tích, lập plan, implement và kiểm chứng các bản fix. Tài liệu này ghi lại các nguyên tắc người dùng đã thống nhất trong phiên làm việc; không tự cấp quyền triển khai những hướng chưa được duyệt.

## 1. Rules chung

1. **Không sửa theo sample hoặc label.** Không dùng sample ID, đáp án reference hay giá trị riêng của case lỗi để quyết định hành vi. Có thể dùng sample làm bằng chứng và test, nhưng production logic không được phụ thuộc vào nó.
2. **Dựa trên quy tắc áp dụng rộng.** Căn cứ phải đến từ yêu cầu người dùng, ý nghĩa tool hoặc dữ kiện agent thực sự nhận được. Không biến đặc điểm ngẫu nhiên của các case đã thấy thành quy tắc chung.
3. **Phân biệt giả thuyết với nguyên nhân đã xác nhận.** Không coi một hướng sửa là hiệu quả khi chưa có bằng chứng; phân biệt ngăn hậu quả với sửa nguyên nhân model sinh sai.
4. **Đưa solution và phạm vi để người dùng review trước khi implement.** Đồng ý về nguyên tắc chưa đồng nghĩa yêu cầu triển khai ngay. Giữ nguyên trạng thái chưa đồng ý/chưa review của từng đề xuất.
5. **Sửa theo từng cụm có liên quan.** Tách thay đổi để có thể xác định nguồn cải thiện hoặc regression. Không gộp các can thiệp không cần thiết vào cùng một bản fix.
6. **Giữ nguyên catalog, runtime chính thức, label và dữ liệu review**, trừ khi người dùng yêu cầu sửa rõ ràng. Phân biệt mô tả bổ sung gửi model với việc thay contract chính thức.

## 2. Rules khi fix bằng code

1. **Không tự đoán thay agent.** Code không tự chọn người, mốc thời gian, nguồn tiền hoặc phương án khi chưa đủ căn cứ. Code có thể thực hiện lựa chọn đã xác định theo quy tắc rõ ràng.
2. **Không tự sửa arguments để khớp đáp án.** Nếu phát hiện sai chắc chắn, trả thông tin lỗi cho agent quyết định bước tiếp theo; không thay bằng giá trị suy đoán.
3. **Chỉ kiểm tra khi đủ bằng chứng.** Chưa biết nguồn không đồng nghĩa sai. Không suy loại ID chỉ bằng tiền tố; phải hỗ trợ alias và cách dùng hợp lệ của tool.
4. **Chuẩn hóa phải giữ nguyên ý nghĩa.** Giữ payload gốc và dấu vết thay đổi. Không biến dữ liệu mơ hồ thành một giá trị chắc chắn hoặc ép chuỗi theo hình dạng phổ biến.
5. **Tách tính toán khỏi lựa chọn ngữ nghĩa.** Code có thể cộng/trừ thời gian từ mốc đã xác định; không tự đoán mốc nào cần dùng.
6. **Không đọc dữ liệu agent không được phép biết.** Không dùng label, hidden state hoặc dữ liệu sample khác để bổ sung đáp án. Được dùng dữ kiện từ input/history/tool-return mà agent được cung cấp.

## 3. Rules khi fix bằng instruction

1. **Viết quy tắc tổng quát.** Nêu nguyên tắc quyết định, tránh liệt kê tình huống chỉ để khớp case đã thấy.
2. **Rõ điều kiện áp dụng và ngoại lệ.** Ví dụ: nhiều kết quả không tự động bắt buộc hỏi; chỉ hỏi khi chưa phân biệt được và chưa được phép chọn tùy ý.
3. **Giữ quyền quyết định của agent.** Hướng dẫn dùng bằng chứng và tuân thủ tool; không ép một chuỗi tool cố định cho mọi yêu cầu. Giới hạn tài nguyên và điều kiện hệ thống đã được thống nhất vẫn áp dụng.
4. **Không thêm quyền hoặc dữ kiện.** Không cho agent tự thêm khoảng đệm thời gian, giá trị hay giả định vượt phạm vi người dùng cho phép. Không cấm các suy luận hợp lệ mà chính sách đã cho phép.
5. **Không lặp hoặc mâu thuẫn với prompt hiện có.** Rà instruction cũ; ưu tiên sửa đoạn chưa rõ thay vì nối thêm quy tắc trùng lặp.
6. **Ngắn, cụ thể, dễ hiểu.** Nêu hành vi bằng từ rõ nghĩa. Ví dụ chỉ minh họa, không trở thành lựa chọn mặc định.

## 4. Rules kiểm chứng

1. Kiểm tra cả case lỗi, case đang đúng và biến thể chưa dùng khi thiết kế. Biến thể phải kiểm tra được ngoại lệ thực sự, không chỉ đổi tên hoặc số.
2. Đánh giá hai chiều: sửa được lỗi nào và làm hỏng trường hợp nào. Khi có replay, báo cáo chuyển đổi từng sample, không chỉ tổng điểm.
3. Offline test xác nhận logic code trong phạm vi đã kiểm; chưa chứng minh model thực hiện tốt hơn.
4. Khi có tài nguyên, so sánh trước/sau trên cùng bộ dữ liệu và cấu hình tương đương. Không tự chạy replay khi người dùng đã yêu cầu bỏ qua.
5. Không cam kết không regression khi chưa đủ kiểm chứng. Ghi rõ giới hạn, phần chưa xác nhận và khả năng quay lại phiên bản trước.

## 5. Đối chiếu 19 hướng fix hiện tại

Nguồn: [report 19 giả thuyết](../review_data/argument_mechanisms_5efb0ae0_20261104/REPORT.md), trường `solution_if_supported` trong `causal_hypotheses.json` và trạng thái `solution_review.json` cùng thư mục. Đây là audit đề xuất, không phải xác nhận implementation đã tuân thủ hoặc model đã cải thiện.

Chưa thấy hướng nào yêu cầu hardcode sample ID hoặc dùng label trong production. Tuy nhiên, các hướng cần thiết kế dưới đây chưa đủ cụ thể để kết luận an toàn trước khi implement.

| Giả thuyết | Đánh giá theo rules | Điều kiện cần giữ hoặc bổ sung |
| --- | --- | --- |
| H-DATE-ISO | Phù hợp về hướng | Đổi cách biểu diễn thứ từ lịch chuẩn, không đổi ngày/phạm vi; kiểm đủ bảy thứ và ranh giới lịch. Đã đồng ý hướng, chưa cho phép implement ở bước này. |
| H-DATE-MEM | Cần thiết kế; chưa được đồng ý | Chưa có cách xác minh nguồn của fact. Không coi kết quả model tự suy là fact đã xác nhận; phải xử lý cập nhật và cách ly từng sample. |
| H-CLOCK-PARSE | Cần thiết kế; chưa được đồng ý | Xác định phạm vi ngôn ngữ hỗ trợ và cách giữ mơ hồ. Không chỉ viết regex cho ba câu đã sai hoặc tự chọn buổi/ngày. |
| H-ANCHOR-ROLE | Cần thiết kế trước phần code | Chưa chốt cách xác định mốc. Code chỉ tính sau khi vai trò/mốc có căn cứ; không dùng keyword tự chọn mốc. |
| H-ANCHOR-MARGIN | Phù hợp về hướng | Không thêm buffer khi user yêu cầu chính xác; giữ ngoại lệ user cho phép chọn giờ. Không đánh đồng hạn chót với giờ thực hiện. Đã đồng ý hướng. |
| H-ID-ROLE | Cập nhật sau review: chỉ sửa instruction | Observer nguồn ID, hook và metadata (Task 6–8) chuyển sang backlog theo quyết định của người dùng. Không viết mapping theo tool hoặc guard trong đợt fixing; instruction giữ cách dùng ID hợp lệ giữa app. |
| H-ID-OPTIONAL | Phù hợp về hướng | Ghi chú đúng hành vi get_ride; không biến lookup chuyến hiện tại thành quyền tự hủy chuyến đó. |
| H-AMBIG-ORDER | Phù hợp về hướng | Không coi thứ tự là tiêu chí nếu chưa được cho phép; giữ trường hợp đã có tiêu chí chọn duy nhất hoặc user cho chọn tùy ý. |
| H-MISSING-EXAMPLE | Cần bằng chứng và giới hạn can thiệp | Không bỏ toàn bộ ví dụ chỉ vì một case chọn số giống ví dụ. Nếu đổi cách trình bày, chỉ đổi lớp model-facing, giữ nguyên ý nghĩa/schema chính thức. |
| H-MISSING-COMMIT | Cần thiết kế trước phần code | Chưa có cách kiểm nguồn cho trạng thái known/unknown. Không bắt mọi giá trị phải xuất hiện nguyên văn: phép tính và suy luận hợp lệ vẫn được dùng. |
| H-LITERAL-REGEN | Cần thiết kế trước phần code | Chốt chuẩn hóa nào giữ nghĩa và cách nhận biết mơ hồ; giữ chuỗi gốc, số đầu 0, số lặp, độ dài hợp lệ. Không tự sửa call bằng chuỗi chưa xác nhận. |
| H-DIMENSION-SLOT | Phù hợp về hướng | Instruction phân biệt đại lượng; chỉ dùng calculator được cấp. Không tự thêm tool hoặc quy tắc chặn số theo ngưỡng tùy ý. |
| H-ENTITY-ATTRIBUTE | Phù hợp về hướng | Giữ tiêu chí nhận diện theo yêu cầu; không tuyệt đối hóa tên hoặc một thuộc tính luôn quan trọng hơn mọi dữ kiện khác. |
| H-CONSTRAINT-CONTRACT | Phù hợp về hướng | Mô tả đúng thanh toán toàn bộ; không tự chuyển nguồn khi chưa được phép. Không coi đây là giải thích cho mọi case CONSTRAINT. |
| H-ENCODE-BOUNDARY | Phù hợp với bước điều tra | Chưa đủ bằng chứng để chọn sửa model/parser. Không tự sửa car7 thành car4 dựa vào một trace. |
| H-CONTENT-DEPEND | Cần thiết kế trước phần code | Chưa có cơ chế nhận biết dependency tổng quát. Không hardcode cặp transfer→SMS, bắt keyword hoặc cấm mọi multi-call; tránh thực thi lặp write khi retry. |
| H-CONTENT-REWRITE | Phù hợp về hướng | Giữ fact nhưng cho phép diễn đạt tương đương; không yêu cầu giống reference. Bảng fact/guard bằng code là thiết kế riêng. |
| H-DEFAULT-AUTHORITY | Cần chốt chính sách | Chưa được phép coi mọi suy luận priority là sai. Thống nhất phạm vi tự chủ trước; không áp quy tắc cấm chung cho mọi tham số optional. |
| H-INTERVAL-SEMANTICS | Phù hợp ở semantic note; guard cần thiết kế | Mô tả đúng partial update. Không tự đặt end=start+1h hoặc tự giữ duration nếu yêu cầu không cho phép. Guard chỉ dùng event agent đã biết. |

Các ô “phù hợp về hướng” không thay thế review diff và kiểm chứng. Những rule còn thiếu chi tiết phải được giải quyết trong plan trước phần implementation tương ứng.
