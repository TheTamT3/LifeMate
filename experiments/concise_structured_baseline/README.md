# Thử nghiệm baseline ngắn và reasoning ba mục

Nhánh: `experiment/concise-structured-baseline`, từ main `4dffca8` sau khi pull. Không phục dựng phiên bản cũ `683907c-dirty`.

## Phạm vi

- Thay các policy dài bằng baseline chung và reasoning **Yêu cầu – Dữ kiện – Quyết định**, thường 1–2 câu/mục. `prompt.txt` là bản xuất nguyên văn của static prompt.
- Phần system động chỉ bổ sung context và lịch suy ra từ current_time, tránh lặp instruction.
- Bỏ semantic note riêng theo tên tool. Giữ description/schema catalog, đối chiếu tên tool chính thức với wire name và hướng dẫn arguments rỗng suy từ schema không tham số.
- Giữ thinking bật, sampling hiện tại, request limit 10 và cách lưu reasoning trong trace. Không thêm tool nội bộ hoặc lượt model.
- Metadata experiment: `prompt_version=vi-concise-structured-v1`, `static_prompt_sha256`, `tool_semantics_notes=false`.

Không sửa official tools, evaluator, label hoặc logic thực thi. Cơ chế chuẩn hóa arguments hiện có vẫn giữ nguyên. Đây là thử nghiệm đồng thời rút prompt và bỏ semantic notes; không cô lập riêng tác động của format reasoning. Format được yêu cầu bằng instruction, không được cưỡng chế bằng parser. Chưa có bằng chứng cải thiện độ chính xác hoặc đáp ứng 30 giây.

## Bộ 20 sample

`sample_ids_20.txt` chọn có chủ đích từ các case lỗi của experiment `06ea4ab6-4fc2-4f43-a019-6f16daafb4f7`. Đây là tập thăm dò, không phải holdout hoặc đại diện ngẫu nhiên của 300 sample. Lý do chọn chỉ để review, không đưa vào prompt.

| Sample | Lỗi đã quan sát |
|---|---|
| train_0032 | Bỏ tra hóa đơn/người thụ hưởng rồi hỏi amount |
| train_0052 | Tự chọn một Minh khi trùng tên |
| train_0066 | 9 giờ kém 15 tối thành 23:45 thay 20:45 |
| train_0071 | Thiếu amount vẫn chuyển tiền; sai tool/ngày báo thức |
| train_0111 | Đặt car7 thay car4 |
| train_0182 | Điều kiện giá không thỏa vẫn tạo reminder |
| train_0247 | Chọn lịch thuốc thay reminder một lần |
| train_0353 | Tự chọn ngày/giờ khi thiếu time |
| train_0511 | Tự thêm repeat daily |
| train_0710 | Arguments email mất dấu chấm |
| train_0787 | Sai ngày ứng với thứ năm |
| train_0908 | Bỏ khoảng đến sớm khi tính giờ rời nhà |
| train_1039 | Bỏ hệ số user cho khi tính mục tiêu bước |
| train_1099 | Tự phát nhạc ngoài yêu cầu |
| train_1192 | Xóa rule dù user đã rút yêu cầu |
| train_1371 | Tool làm đúng nhưng lỗi kết thúc phản hồi |
| train_1394 | Tự đánh dấu cảnh báo đã xem |
| train_1510 | Không log hai thuốc đã uống |
| train_1547 | Trả giá đơn thứ sáu thay đơn thứ tư |
| train_1673 | Truy vấn rỗng nhưng vẫn gợi ý quán chưa xác minh |

## Chạy trên server

Lấy nhánh thử nghiệm, dùng môi trường Python và vLLM đang hoạt động:

```bash
cd /workspace/LifeMate
git fetch origin
git switch experiment/concise-structured-baseline
git pull --ff-only
```

Lệnh dưới dùng alias `qwen3-4b` như các lần chạy trước. Kiểm tra `/v1/models` và đổi `--llm-model-name` nếu alias hiện tại là `qwen3.5-4b`. Đường dẫn `--model` phải khớp thư mục model local thực tế.

```bash
PYTHONPATH=src python scripts/smoke_e2e_langsmith.py \
  --root data/validation_300 \
  --split train \
  --sample-ids-file experiments/concise_structured_baseline/sample_ids_20.txt \
  --model models/qwen3.5-4b \
  --use-reference-text \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model-name qwen3-4b \
  --dataset-name lifemate-validation300-train \
  --experiment-name "lifemate-concise-structured-20-$(date +%Y%m%d-%H%M%S)" \
  --max-steps 10 \
  --seed 0
```

Không thêm `--limit`: selector đó loại trừ `--sample-ids-file`. Dataset server cần đủ 20 sample, catalog và environment; script kiểm tra ID và dựng reference trước khi gọi model. Local không có thư mục `data/validation_300`; bộ ID được đối chiếu với train gốc và snapshot experiment 300 sample.

Đánh giá state hash, tool call, runtime error, latency và reasoning thực tế. Giữ cùng model weights, sampling và concurrency để so sánh. Không suy tỷ lệ toàn bộ 300 từ 20 case đã chọn. Chưa chạy inference/replay ở local.
