# Thiết kế đánh giá ASR tiếng Việt

## 1. Mục đích

Tạo một pipeline độc lập để đo chất lượng `khanhld/chunkformer-ctc-large-vie` trên dữ liệu train có sẵn audio và transcript chuẩn trong trường `audio_text`. Pipeline này giúp tách lỗi nhận dạng tiếng nói khỏi lỗi LLM và tool-calling trong baseline chính.

## 2. Phạm vi

### Mục tiêu

- Đọc sample từ `train/train.jsonl`.
- Resolve đường dẫn audio tương đối theo thư mục split.
- Chạy ASR local/offline trên từng audio.
- So sánh transcript dự đoán với `audio_text`.
- Tính WER, CER, exact-match và latency.
- Lưu kết quả chi tiết theo sample và báo cáo tổng hợp, dùng UTF-8.
- Hỗ trợ chạy toàn bộ dataset hoặc giới hạn số sample để smoke test.

### Không thuộc phạm vi

- Không gọi LLM, PydanticAI, `ToolEnv` hoặc các tool của app.
- Không dùng transcript dự đoán làm input cho baseline trong cùng pipeline.
- Không fine-tune ASR.
- Không gọi API hoặc dịch vụ bên ngoài khi đánh giá.

## 3. Các phương án đã cân nhắc

1. **CLI độc lập (được chọn):** reproducible, dễ chạy local/Colab, đo được thời gian ASR riêng và không làm baseline chính nặng hơn.
2. **Nhúng vào baseline:** một lệnh duy nhất nhưng trộn latency/lỗi ASR với LLM và khó chẩn đoán.
3. **Notebook phân tích:** tiện xem lỗi thủ công nhưng không phù hợp làm pipeline đánh giá chuẩn.

CLI độc lập được chọn vì mục tiêu hiện tại là xác định chất lượng ASR trước khi tối ưu các phần còn lại.

## 4. Thiết kế thực thi

Tạo module/CLI `lifemate.asr_eval` (tên cụ thể có thể điều chỉnh theo cấu trúc repo). CLI nhận:

- `--root`: thư mục chứa `train/`.
- `--split`: mặc định `train`.
- `--asr-model`: thư mục checkpoint local.
- `--output`: đường dẫn file prediction JSONL.
- `--report`: đường dẫn report JSON.
- `--limit`: số sample tối đa, tùy chọn.
- `--device`: `auto`, `cpu` hoặc thiết bị do package ChunkFormer hỗ trợ.
- `--batch-size`: số audio xử lý trong một batch, mặc định `1` (tuần tự).
- `--seed`: để giữ hành vi reproducible nếu runtime có thành phần ngẫu nhiên.

Mặc định mỗi sample được xử lý tuần tự theo thứ tự file JSONL. Khi `--batch-size > 1`, runner gom các sample thành batch và chỉ bật chế độ này nếu adapter/package ChunkFormer hỗ trợ batch inference; kết quả vẫn phải giữ `id` và thứ tự input để đối chiếu. Dùng một instance `ChunkFormerASR` dùng chung để tránh load model lặp lại. Batch không được làm thay đổi metric; nếu batch lỗi do thiếu bộ nhớ hoặc lỗi một audio, runner phải fallback về xử lý tuần tự batch đó và ghi cảnh báo. Audio lỗi hoặc sample thiếu trường bắt buộc phải được ghi là lỗi trong output và không làm mất các sample đã xử lý; cuối cùng CLI trả mã lỗi khác 0 nếu có sample lỗi.

## 5. Chuẩn hóa và metric

Giữ cả transcript raw và transcript đã chuẩn hóa. Chuẩn hóa dùng Unicode NFC, chuyển khoảng trắng liên tiếp thành một khoảng trắng và trim đầu/cuối; không tự động bỏ dấu hoặc đổi chữ thường trong bản raw. Metric được tính trên bản chuẩn hóa:

- **WER:** edit distance ở mức từ / số từ của transcript chuẩn.
- **CER:** edit distance ở mức ký tự / số ký tự của transcript chuẩn.
- **Exact match:** transcript chuẩn hóa dự đoán bằng transcript chuẩn hóa nhãn.
- **Fuzzy token F1:** token precision/recall/F1 trên transcript relaxed; `fuzzy_match` là true khi F1 `>= 0.8`.
- **Latency:** thời gian từ trước khi gọi ASR đến sau khi nhận kết quả, tính bằng giây.

Với transcript chuẩn rỗng, cần quy ước rõ: prediction rỗng là đúng; prediction không rỗng bị tính là lỗi toàn phần. Report phải nêu số sample hợp lệ và số sample lỗi để tránh làm sai trung bình.

## 6. Định dạng output

`asr_predictions.jsonl`, mỗi dòng gồm:

```json
{
  "id": "train_0001",
  "audio": "audio/train_0001/train_0001.wav",
  "reference": "...",
  "prediction": "...",
  "reference_normalized": "...",
  "prediction_normalized": "...",
  "wer": 0.0,
  "cer": 0.0,
  "exact_match": true,
  "fuzzy_token_f1": 1.0,
  "fuzzy_match": true,
  "latency_seconds": 1.23,
  "error": null
}
```

Nếu sample lỗi, giữ `id`, `audio`, các trường transcript nếu có, đặt metric là `null` và ghi thông báo ở `error`.

`asr_report.json` gồm tổng số sample, số thành công/lỗi, WER/CER strict trung bình, WER/CER relaxed trung bình, fuzzy token F1 trung bình, strict/relaxed/fuzzy match rate, latency trung bình, latency p95 và các đường dẫn input/model/output. Trung bình metric chỉ tính trên sample chạy thành công.

## 7. Kiểm thử và xác nhận

- Unit test cho Unicode NFC, whitespace, WER/CER, exact match và transcript rỗng.
- Test CLI với fake ASR để không cần model thật.
- Test đường dẫn audio và ghi JSONL UTF-8 (`ensure_ascii=False`).
- Smoke test một sample thật trên local/Colab.
- Smoke test với `--batch-size 1` và một batch lớn hơn trên GPU đủ bộ nhớ; xác nhận kết quả metric giống chế độ tuần tự.
- Chạy toàn bộ train sau khi smoke test thành công; kiểm tra report parse được và không có output bị mojibake.

## 8. Tiêu chí hoàn thành

Pipeline chạy được offline với checkpoint local, tạo đủ hai file output, kết quả lặp lại ổn định trên cùng môi trường, và cung cấp metric để quyết định có cần tối ưu ASR trước khi đánh giá LLM hay không.
