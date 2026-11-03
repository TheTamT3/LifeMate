# Error Mechanism Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user chooses delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Execution status (2026-11-03):** Tasks 1–10 implemented and verified offline; conditional commit steps remain unchecked because no commit was requested. See [remediation results](../../ERROR_MECHANISM_REMEDIATION_RESULTS.md). `train_1533` retains V01/R03/Q01 memberships from the source crosswalk; `train_1449` maps to R07.

**Goal:** Xử lý có kiểm chứng toàn bộ các cụm trong báo cáo tổng hợp, trừ R01 đã sửa, ưu tiên can thiệp code có căn cứ trước instruction và giữ nguyên chuẩn chấm chính thức.

**Architecture:** Chia thành ba phần có thể review độc lập: bộ kiểm chứng offline và contract; hỗ trợ thời gian và instruction dùng chung; tổng kết phạm vi cùng các kết luận còn mở. Mỗi thay đổi chỉ sửa cơ chế có bằng chứng, không tạo bộ luật suy đoán ý định thay agent. Các cụm đối chứng, chính sách và thiếu bằng chứng được xử lý bằng test hoặc quyết định có tài liệu thay vì ép thành bug code.

**Tech Stack:** Python, pytest, Pydantic/PydanticAI hiện có, datetime/calendar chuẩn Python, simulator `zaic_tools` chính thức ở chế độ đọc nguồn và chạy state tạm.

**Spec:** [ERROR_MECHANISM_SYNTHESIS_20261103.md](../../ERROR_MECHANISM_SYNTHESIS_20261103.md), [ERROR_MECHANISM_FIX_PLAN.md](../../ERROR_MECHANISM_FIX_PLAN.md), và yêu cầu người dùng trong phiên: ưu tiên code, duyệt solution trước implement, không cần replay LLM.

## Global Constraints

- Phạm vi: 14 cụm tổng hợp từ 97 bucket/192 sample của 12 nhóm đã điều tra; không tuyên bố đã bao phủ mọi lỗi của 300 sample.
- **P01/R01:** bỏ qua sửa mới R01. Chỉ 21 sample của `P01:pipeline` thuộc R01; 22 sample hỗn hợp X01 không mặc nhiên đã được fix.
- Giữ solution R01 hiện có: agent quyết định tiếp tục/kết thúc, chỉ pause sau nhóm tool có `sys.ask_missing_info`, mặc định **10 model request**, cho phép override.
- README `train+public_test/train+public_test/train/zaic_tools/README.md`: “Không sửa gói này hay `*_environment/`: server luôn dùng bản gốc.” Không sửa simulator, catalog gốc, state, label hoặc reference để làm điểm tốt hơn.
- Giữ nguyên review/comment/verdict/feedback và các file snapshot, error_analysis, group_causes, SQLite hiện hành. Chỉ đọc evidence và xuất artifact riêng.
- Không gọi LLM, không replay 300 sample, không cần GPU trong các task dưới đây. Scripted model/fake tool dùng để kiểm tra wiring, không chứng minh model làm đúng.
- Không cam kết accuracy tăng, không cam kết end-to-end dưới **30 giây** từ test offline. Giới hạn request 10 không phải time budget.
- Không thêm dependency, tool ngoài catalog, heuristic tự chọn người/ID/giờ, tự bỏ filter, tự sửa payload có tham số hoặc chặn write trùng.
- Giữ `tool_call_accuracy` và `state_hash_match` hiện tại; diễn giải thủ công không ghi đè điểm chính thức. README mô tả call F1 của BTC, local evaluator hiện dùng binary full-call-set; không gọi hai metric này là một.
- Chỉ sửa instruction theo nguyên tắc tổng quát; không nhúng sample ID, ngày, tên người, giá trị label hoặc danh sách case vào prompt.
- Mỗi task là một đơn vị review/rollback. Chỉ thực hiện bước commit khi người dùng yêu cầu; không tự push. Không stage các thay đổi R01 hoặc file không thuộc task.
- Kế hoạch này là đề xuất thay thế thứ tự đợt cũ: **code có căn cứ → instruction từng cơ chế → tổng kết**. Chưa implement khi chưa được người dùng duyệt.

## Review Focus

1. Sample đồng thời thuộc V01 và R03: một khác biệt hợp lệ không được làm cả sample thành đúng — Task 1/10 có test overlap.
2. Runtime chuẩn bỏ qua `limit`: mô tả bổ sung không được đổi schema, arguments, thứ tự hay số bản ghi — Task 2 có test contract và bất biến catalog.
3. Email hợp lệ, khoảng trắng và địa chỉ đọc bằng lời: format validator chỉ kiểm chuỗi đã có, không tự sinh địa chỉ/người nhận — Task 3/9 có test format và preservation.
4. Context thời gian thiếu/sai offset, giao năm hoặc mốc sự kiện vừa đổi: không dùng đồng hồ máy thay evidence; bảng lịch không tự quyết định anchor — Task 4/8 có test tương ứng.
5. Điều kiện trong nội dung cần gửi và yêu cầu đã rút: instruction phải phân biệt nội dung với lệnh, không sửa history hay tự chặn tool — Task 6/7 có test dữ liệu nguyên vẹn và scenario đối chứng.

---

## Phạm vi, trạng thái và thứ tự

“Xử lý” gồm sửa bug được chứng minh, hỗ trợ model hoặc chốt cách diễn giải. **Không đồng nghĩa mọi sample trong một cụm sẽ được sửa đúng bởi bản code này.**

| Cụm | Tình trạng hiện tại | Hướng xử lý | Task |
|---|---|---|---|
| R01 | Đã sửa local; tích hợp model thật chưa xác minh | Không sửa lại; giữ regression hiện có | Ngoài scope sửa mới |
| C01 · 2 sample | `order_history.limit` có trong schema nhưng runtime bỏ qua; runtime là chuẩn BTC | Characterization test + mô tả chính xác cho model; không implement limit | 2 |
| R08 · 1 | Sai literal nói; validator email có pattern cần kiểm chứng bằng test | Sửa validator nếu test chứng minh bug; instruction không tự thêm địa chỉ | 3, 9 |
| R06 · 21 | Sai nghĩa thời gian; format hợp lệ không đủ | Bảng lịch xác định từ context + instruction về anchor/phép dịch chuyển | 4, 8 |
| R07 · 7 | Chủ yếu model chọn filter sai; chưa chứng minh serializer tạo `"None"` | Test truyền arguments, mô tả semantics, instruction về phạm vi bằng chứng | 5 |
| R02 · 19 | Chọn sai nghiệp vụ/nguồn/tác dụng | Mô tả tool được đối chiếu runtime + instruction chọn đúng tác dụng | 2, 9 |
| R03 · 29 | Tự chọn hoặc điền thiếu căn cứ | Instruction về nguồn dữ kiện, tra cứu và hỏi thiếu thông tin | 9 |
| R04 · 19 | Không giữ điều kiện trước write | Instruction về điều kiện và phạm vi thao tác; không dùng keyword guard | 6 |
| R05 · 8 | Mất ý định sau sửa/rút | Instruction giữ yêu cầu cuối, regression history nguyên vẹn | 7 |
| R09 · 3 | Model tự thêm optional operational values; label có thể mâu thuẫn | Kiểm tra omit-vs-explicit; instruction giới hạn tự điền | 9 |
| V01 · 83 | Khác biệt hợp lệ cục bộ; không chứng minh toàn sample đúng | Đối chứng theo hiện tượng, giữ metric chính thức | 1, 10 |
| Q01 · 33 | Phụ thuộc state hoặc chính sách chưa chốt | Ghi chính sách và trạng thái unresolved; không đổi scorer | 10 |
| X01 · 22 | Hỗn hợp model/pipeline | Ánh xạ sang cơ chế cụ thể; thiếu bằng chứng thì giữ mở | 10 |
| X02 · 3 | Thiếu evidence/ngoài scope/write chưa xảy ra | Ghi giới hạn kết luận; không tạo fix chung | 10 |

Các số sample chồng lấp, không cộng để tính số được fix. Ưu tiên code ở Task 1–4 không có nghĩa đã chứng minh các cụm tương ứng do pipeline.

## Bản đồ file và ranh giới trách nhiệm

| File | Trách nhiệm |
|---|---|
| `tests/fixtures/mechanism_cases.json` (mới) | Manifest ID/cụm/bucket, bằng chứng tối thiểu và kết luận cục bộ; chỉ phục vụ test, không làm input agent |
| `tests/test_mechanism_cases.py` (mới) | Coverage 13 cụm còn lại, overlap, schema manifest, không thiếu crosswalk |
| `src/lifemate/tool_semantics.py` (mới) | Mô tả bổ sung đã xác minh, không đổi schema/arguments/runtime |
| `tests/test_tool_semantics.py` (mới) | Mô tả đúng tool, không lan sang tool khác và không mutation |
| `tests/test_tool_contracts.py` (mới) | Characterization runtime bằng state tạm; lọc, default, limit, done=false |
| `src/lifemate/time_context.py` (mới) | Bảng ngày/thứ hữu hạn từ `context.current_time`, không phân tích ý định |
| `tests/test_time_context.py` (mới) | Tính ngày, giao tháng/năm, offset và context thiếu/sai |
| `src/lifemate/agent_policy.py` (mới) | Các đoạn instruction theo cơ chế, ghép thành một policy dùng chung |
| `tests/test_agent_policy.py` (mới) | Exact policy copy, thứ tự, không nội dung case; chỉ kiểm wiring/copy |
| `src/lifemate/pydantic_agent.py` | Dùng policy, description bổ sung; sửa email format nếu test đỏ chứng minh |
| `src/lifemate/runner.py` | Thêm time facts vào dynamic system context; không sửa user/history |
| `tests/test_pydantic_agent.py`, `tests/test_history_prompt.py`, `tests/test_runner.py` | Wiring, arguments, message history, không lộ label/state |
| `docs/ERROR_MECHANISM_REMEDIATION_RESULTS.md` (mới) | Quyết định Q01, trạng thái từng cụm, test/result/giới hạn và nội dung chưa xác minh |

Không sửa `prompting.py`: đây là builder JSON cũ, đường chạy PydanticAI đang dùng `_build_system_prompt()` và `build_agent()`.

## Task 1: Khóa phạm vi và tạo manifest đối chứng offline

**Files:** Create `tests/fixtures/mechanism_cases.json`, `tests/test_mechanism_cases.py`.

**Interfaces:** Manifest là list object `{sample_id: str, cluster: str, bucket: str, finding: str, scope: str, evidence: str}`. `scope` chỉ nhận `local_difference`, `action_sequence`, `unresolved`. Không định nghĩa một boolean “sample đúng” từ membership. Nguồn là bảng nguồn trong spec và evidence hiện có, không tự suy từ tên nhóm.

- [ ] **Step 1: Viết test đỏ** `test_manifest_covers_remaining_clusters`: tập cluster đúng bằng `{R02,R03,R04,R05,R06,R07,R08,R09,V01,Q01,C01,X01,X02}`; mỗi cụm có ít nhất một case và evidence không rỗng. `test_overlap_is_not_whole_sample_success`: `train_1533` giữ V01, R03 và Q01 theo crosswalk; V01 có scope `local_difference`, không có trường `whole_sample_correct`.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_mechanism_cases.py -q`; expected fail vì fixture chưa tồn tại.
- [ ] **Step 3: Tạo manifest:** chọn case đại diện nêu ở từng task dưới đây; trích evidence và kết luận reviewer đã chốt. Giữ case bất đồng theo comment cũ đúng như người dùng đã quyết định; không sửa nguồn review. Thêm 83 V01 membership vào manifest để không chọn đối chứng chỉ vì trùng state.
- [ ] **Step 4: Chạy xanh:** cùng lệnh; expected pass, mọi membership V01 của spec có entry và không bị gán đúng toàn bộ. Test chỉ kiểm manifest, không đọc SQLite live.
- [ ] **Step 5: Commit khi được yêu cầu:** chỉ stage hai file của task; message `test: establish mechanism regression manifest`.

## Task 2: C01 và semantics tool đã xác minh

**Files:** Create `src/lifemate/tool_semantics.py`, `tests/test_tool_semantics.py`, `tests/test_tool_contracts.py`; Modify `src/lifemate/pydantic_agent.py:build_tool_definitions`.

**Interfaces:** `tool_semantics_note(name: str) -> str` trả note hoặc `""`; append vào description hiện có, không mutate tool dictionary. Các note chỉ áp dụng đúng official name. `build_tool_definitions(deps)` giữ signature và wire mapping.

- [ ] **Step 1: Viết test đỏ:** `test_order_history_note_documents_ignored_limit`, `test_unknown_tool_has_no_note`, `test_description_overlay_preserves_catalog_and_arguments`. Với state tạm có 3 orders, `food_delivery.order_history(limit=1)` vẫn trả cùng toàn bộ orders như bỏ limit, theo thứ tự runtime, cho `train_1499/1547` làm evidence. Test dùng fixture riêng, không chạy trên environment gốc. Thêm characterization cho autopay không trả bill hiện tại, quote không booking, update không phục hồi sự kiện canceled; bám đúng envelope runtime đã đọc.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_tool_semantics.py tests/test_tool_contracts.py -q`. Characterization có thể xanh sẵn; phải có test overlay đỏ vì API chưa tồn tại.
- [ ] **Step 3: Implement API** và bốn note với tên đã đối chiếu catalog: `food_delivery.order_history` — “Runtime hiện tại không áp dụng limit; cần xét toàn bộ đơn trả về, không suy ra chỉ có limit đơn.”; `bill_payment.schedule_autopay` — cấu hình không thanh toán bill hiện tại; `ride_hailing.get_quotes` — báo giá chưa đặt xe; `calendar.update_event` — không tự khôi phục canceled. Không xóa tham số limit, không cắt output.
- [ ] **Step 4: Chạy xanh:** lệnh Step 2 cùng `python -m pytest tests/test_pydantic_agent.py -q`. Expected pass; deep equality catalog trước/sau, env nhận đúng arguments gốc. Nếu runtime source không có ở checkout, báo missing prerequisite, không fake PASS cho contract test.
- [ ] **Step 5: Commit khi được yêu cầu:** các file của task; message `fix: clarify verified tool runtime semantics`.

## Task 3: R08 — sửa bug format có thể kiểm chứng bằng code

**Files:** Modify `src/lifemate/pydantic_agent.py:_validate_formats`, `tests/test_pydantic_agent.py`.

**Interfaces:** `validate_catalog_arguments(tool, arguments) -> dict` giữ nguyên. Email format chỉ validate, không normalize/parse lời nói.

- [ ] **Step 1: Viết test đỏ** `test_email_format_accepts_valid_literal`: schema email với `a.b+tag@example.com` trả đúng chuỗi. `test_email_format_rejects_whitespace_and_missing_domain`: `a b@example.com`, `a@example`, `a@b.com\n`, `a@@b.com` phải raise ValueError. `test_email_validation_never_adds_recipients`: array email có một phần tử vẫn một phần tử, input không mutation.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_pydantic_agent.py -k email -q`; xác nhận fail từ regex hiện tại, không từ fixture/import. Nếu test xanh hết, không sửa regex, ghi “không có bug tái hiện”.
- [ ] **Step 3: Sửa tối thiểu pattern email** bằng `re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)`. Đây là format check tối thiểu theo contract hiện có, không phải RFC parser. Không sửa text transcript hoặc thêm người nhận; lỗi model của `train_0681` vẫn cần Task 9.
- [ ] **Step 4: Chạy xanh:** `python -m pytest tests/test_pydantic_agent.py -q`; valid literal qua và malformed literal bị chặn trước env.call.
- [ ] **Step 5: Commit khi được yêu cầu:** hai file; message `fix: validate literal email whitespace correctly`.

## Task 4: R06 — thêm bảng lịch xác định từ context

**Files:** Create `src/lifemate/time_context.py`, `tests/test_time_context.py`; Modify `src/lifemate/runner.py:_build_system_prompt`, `tests/test_history_prompt.py`.

**Interfaces:** `build_time_context(context: dict[str, Any]) -> dict[str, Any]`. Output hợp lệ gồm `anchor` (ISO đầu vào), `today`, `tomorrow`, `day_after_tomorrow` (ISO date), `calendar` (14 object `{date, iso_weekday}` của tuần hiện tại và tuần kế, tuần bắt đầu thứ Hai). Thiếu/sai `current_time` hoặc timestamp không có offset → `{}`. Không dùng clock máy, không lấy state/label. Offset timestamp là nguồn tính ngày; giữ timezone label ở context gốc, không tự chuyển múi giờ khi offset/name mâu thuẫn.

- [ ] **Step 1: Viết test đỏ:** `test_calendar_uses_sample_time` dùng `2026-11-03T23:30:00+07:00`, assert today `2026-11-03`, tomorrow `2026-11-04`, day_after `2026-11-05`, 14 ngày từ `2026-11-02` đến `2026-11-15`, thứ Hai iso_weekday=1. `test_calendar_crosses_year` dùng `2026-12-31T23:30:00+07:00`, tomorrow=`2027-01-01`. `test_invalid_or_naive_anchor_has_no_fallback` assert `{}` cho thiếu/invalid/naive. `test_offset_date_is_not_host_date` giữ local date dù UTC khác ngày.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_time_context.py -q`; expected import failure của module mới.
- [ ] **Step 3: Implement helper** bằng `datetime.fromisoformat`, `timedelta` và `isoweekday`. `_build_system_prompt()` append block `Mốc lịch suy ra từ context: <JSON>` chỉ khi helper trả nonempty. Không thay text user/history; context gốc vẫn có đủ dữ kiện.
- [ ] **Step 4: Chạy xanh:** `python -m pytest tests/test_time_context.py tests/test_history_prompt.py -q`; thêm assert label và hidden state không xuất hiện trong system prompt. Bảng này hỗ trợ quy đổi thứ/ngày, **chưa giải quyết chọn anchor, giờ kém, dịch giờ hoặc timezone conflict**; Task 8 xử lý bằng instruction.
- [ ] **Step 5: Commit khi được yêu cầu:** các file của task; message `feat: derive bounded calendar facts from sample context`.

## Task 5: R07 — bảo toàn arguments và làm rõ phạm vi query

**Files:** Create `src/lifemate/agent_policy.py`, `tests/test_agent_policy.py`; Modify `src/lifemate/pydantic_agent.py:build_agent`, `src/lifemate/tool_semantics.py`, `tests/test_pydantic_agent.py`, `tests/test_tool_contracts.py`.

**Interfaces:** `BASE_POLICY: str` chứa nguyên instruction base hiện tại; `QUERY_POLICY: str`; `agent_instructions() -> str` ghép các policy bằng newline, thứ tự BASE rồi các policy đã triển khai. `build_agent()` dùng function này một lần thay literal hiện tại; giữ VIETNAMESE_REASONING. Các task sau thêm constants vào cùng function, không tạo thêm system message.

- [ ] **Step 1: Viết test đỏ cho wiring policy**, đồng thời characterization: thiếu tracking_id giữ omit, chuỗi `"None"` giữ literal, không convert thành null; query since=current_time bỏ các alert trước đó; filter loại thiết bị chỉ trả loại đó. Assert kết quả rỗng không làm wrapper tự query rộng hoặc tự write. Dùng case 0676/1105/1449 và state tổng hợp làm đối chiếu.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_agent_policy.py tests/test_pydantic_agent.py tests/test_tool_contracts.py -q`; expected policy mới chưa tồn tại, các preservation test có thể xanh sẵn.
- [ ] **Step 3: Implement policy và note semantics** từ source runtime; exact QUERY_POLICY: “Chỉ dùng bộ lọc có căn cứ từ yêu cầu hoặc dữ kiện đã xác nhận. Kết quả rỗng chỉ mô tả truy vấn đã gọi; trước khi kết luận không có đối tượng, kiểm tra truy vấn có bao phủ phạm vi cần thiết hay không. Nếu cần tra cứu lại, điều chỉnh bộ lọc theo yêu cầu và schema, không mặc định bỏ mọi bộ lọc. Không dùng chuỗi None hoặc null để biểu diễn tham số chưa biết; chỉ bỏ tham số khi schema cho phép.” Note since là cận dưới, tracking ID là exact lookup theo semantics source. Không thêm retry heuristic hoặc sửa `"None"` tự động.
- [ ] **Step 4: Chạy xanh:** cùng lệnh; fake Agent bắt được instruction, policy xuất hiện một lần trong static instructions, catalog/payload giữ nguyên. Đây là kiểm tra wiring/contract, không chứng minh model đã query đúng.
- [ ] **Step 5: Commit khi được yêu cầu:** file task; message `feat: clarify query coverage without rewriting arguments`.

## Task 6: R04 — điều kiện quyết định hành động

**Files:** Modify `src/lifemate/agent_policy.py`, `tests/test_agent_policy.py`, `tests/test_history_prompt.py`, `tests/fixtures/mechanism_cases.json`.

**Interfaces:** Thêm `CONDITION_POLICY: str` sau QUERY_POLICY trong `agent_instructions()`; giữ mọi chữ ký trước đó.

- [ ] **Step 1: Viết test đỏ** cho exact policy copy và wiring. Bổ sung scenario vào manifest: 0533 condition false không heat; 0190 loại bill vượt ngưỡng; 0107 không tự chia thanh toán; control yêu cầu không điều kiện; control câu có chữ “nếu” nằm trong nội dung gửi. Test builder giữ nguyên văn message content và request. **Không đặt test “model sẽ hiểu đúng” khi chỉ dùng fake.**
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_agent_policy.py tests/test_history_prompt.py tests/test_mechanism_cases.py -q`; expected thiếu CONDITION_POLICY.
- [ ] **Step 3: Thêm exact copy:** “Phân biệt điều kiện cần kiểm tra với dữ kiện đã được xác nhận. Trước thao tác phụ thuộc điều kiện, lấy đủ thông tin và chờ kết quả cần thiết để xác định điều kiện có thỏa mãn không. Chỉ thực hiện thao tác được yêu cầu khi điều kiện áp dụng cho nó đã thỏa mãn; giữ đúng phủ định, so sánh, phạm vi và thứ tự ưu tiên. Không tự thêm, thay thế hoặc kết hợp thao tác ngoài yêu cầu. Điều kiện nằm trong nội dung người dùng muốn gửi hoặc lưu là nội dung, trừ khi người dùng yêu cầu dùng nó để quyết định hành động. Những việc độc lập vẫn có thể tiếp tục.” Không hardcode bill/weather/smart_home hoặc parser keyword.
- [ ] **Step 4: Chạy xanh:** lệnh Step 2; ghi riêng acceptance scenario chưa kiểm chứng bằng LLM. Không dùng scripted action để tuyên bố prompt fix thành công.
- [ ] **Step 5: Commit khi được yêu cầu:** file task; message `feat: state general conditional action policy`.

## Task 7: R05 — giữ ý định cuối cùng và lời rút yêu cầu

**Files:** Modify `src/lifemate/agent_policy.py`, `tests/test_agent_policy.py`, `tests/test_history_prompt.py`, `tests/fixtures/mechanism_cases.json`.

**Interfaces:** Thêm `INTENT_POLICY: str` sau CONDITION_POLICY. Không thêm object “intent” do code tự suy ra.

- [ ] **Step 1: Viết test đỏ** policy và test history nhiều lượt: lời sửa/rút, assistant call và tool result có cùng tool_call_id, current request vẫn là user message cuối. Assert không xóa ý định cũ khỏi history và không đổi lời rút thành tool action. Manifest bao phủ 0957/1084/1286 và control lời sửa chỉ một tham số, không rút cả tác vụ.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_agent_policy.py tests/test_history_prompt.py tests/test_mechanism_cases.py -q`; expected thiếu INTENT_POLICY, không sửa logic history nếu preservation đã pass.
- [ ] **Step 3: Thêm exact copy:** “Xác định yêu cầu còn hiệu lực từ toàn bộ hội thoại và lời sửa hoặc rút lại mới nhất. Chỉ thay phần người dùng đã sửa; giữ các phần còn hiệu lực. Sau mỗi lần tra cứu, tiếp tục theo yêu cầu đã cập nhật. Không thực hiện hoặc hỏi tham số cho thao tác đã bị rút. Khi cách thực hiện mới không khả dụng, không tự quay lại yêu cầu hoặc cách thực hiện đã bị thay thế; chỉ tra cứu hoặc hỏi thông tin cần cho yêu cầu còn hiệu lực.”
- [ ] **Step 4: Chạy xanh:** lệnh Step 2; history giữ nguyên, static instructions có policy đúng một lần. Không thêm stop/block dựa keyword “thôi”.
- [ ] **Step 5: Commit khi được yêu cầu:** file task; message `feat: preserve latest active intent in agent policy`.

## Task 8: R06 — hướng dẫn chọn mốc và quy đổi thời gian

**Files:** Modify `src/lifemate/agent_policy.py`, `tests/test_agent_policy.py`, `tests/test_history_prompt.py`, `tests/fixtures/mechanism_cases.json`.

**Interfaces:** Thêm `TIME_POLICY: str` sau INTENT_POLICY; dùng output Task 4 như thông tin tham khảo, không bắt buộc mọi ngày nằm trong bảng.

- [ ] **Step 1: Viết test đỏ** policy và preservation: context hiện tại, event time từ tool result và event time đã update đều còn nguyên; bảng ngày không thay giá trị write do model gửi. Manifest: 0546 thứ/ngày, 0124 anchor sau update, 0381 hướng dịch, 0247 giờ đọc, 0033 cần tra event; control giữ ngày user nêu rõ, timestamp ngoài bảng, timezone name/offset mâu thuẫn.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_agent_policy.py tests/test_time_context.py tests/test_history_prompt.py tests/test_pydantic_agent.py -q`; expected thiếu TIME_POLICY.
- [ ] **Step 3: Thêm exact copy:** “Dùng thời gian trong context làm mốc hiện tại, không dùng ngày giờ ví dụ trong schema. Với thời điểm phụ thuộc sự kiện hoặc kết quả thao tác trước, tra cứu và dùng mốc đã được xác nhận hoặc cập nhật. Giữ đúng ngày giờ người dùng nêu rõ; khi quy đổi, kiểm tra thứ/ngày, sáng/tối, khoảng thời gian, hướng cộng trừ và múi giờ. Bảng lịch suy ra từ context chỉ hỗ trợ đối chiếu ngày/thứ, không quyết định sự kiện nào là mốc. Nếu cách nói thời gian hoặc các mốc mâu thuẫn mà chưa xác định được nghĩa, hỏi lại thay vì tự chọn.”
- [ ] **Step 4: Chạy xanh:** lệnh Step 2; case ngoài bảng vẫn truyền timestamp nguyên vẹn; không âm thầm gán timezone hoặc dịch “lùi” bằng keyword. Ghi phần arithmetic/semantic chưa được chứng minh model cải thiện.
- [ ] **Step 5: Commit khi được yêu cầu:** file task; message `feat: clarify temporal anchors and conversions`.

## Task 9: R02/R03/R08/R09 — tác dụng tool, grounding và giá trị optional

**Files:** Modify `src/lifemate/agent_policy.py`, `tests/test_agent_policy.py`, `tests/test_pydantic_agent.py`, `tests/test_tool_contracts.py`, `tests/fixtures/mechanism_cases.json`.

**Interfaces:** Thêm `EVIDENCE_POLICY: str` sau TIME_POLICY. Đây là phần duy nhất dùng chung cho lựa chọn tool/nguồn/optional; không tạo bốn instruction lặp nhau.

- [ ] **Step 1: Viết test đỏ** policy. Thêm contract/preservation tests: omitted climate temperature giữ nhiệt độ hiện tại; explicit temperature=26 vẫn được truyền và thực thi, không bị wrapper bỏ; omitted priority giữ runtime default normal; explicit priority không bị tự sửa. Scenario manifest: 0088/0817/1141 chọn tool; 0116/1292 thiếu/mơ hồ; R07 0676/1105/1449 query coverage/ID; 0681 literal một người nhận; 0643/1123/0103 optional/label. Control đủ một ID đã xác nhận không cần hỏi; nhiều ứng viên không tự chọn đầu tiên; yêu cầu explicit cho optional phải được giữ.
- [ ] **Step 2: Chạy đỏ:** `python -m pytest tests/test_agent_policy.py tests/test_pydantic_agent.py tests/test_tool_contracts.py tests/test_mechanism_cases.py -q`; expected thiếu EVIDENCE_POLICY; preservation test có thể xanh sẵn.
- [ ] **Step 3: Thêm exact copy:** “Chọn công cụ theo nguồn dữ liệu và tác dụng được mô tả: đọc thông tin, cấu hình và thực hiện thao tác là các tác dụng khác nhau. Chỉ dùng giá trị từ yêu cầu, context, hội thoại hoặc kết quả công cụ đã xác nhận đúng đối tượng; ví dụ trong schema không phải dữ kiện. Tra cứu khi công cụ có thể cung cấp thông tin còn thiếu; khi chưa đủ căn cứ hoặc còn nhiều ứng viên phù hợp, hỏi qua sys.ask_missing_info về phần cần làm rõ, không tự chọn ứng viên hay tiêu chí. Khi dữ liệu đã đủ và rõ, thực hiện mà không hỏi lại thừa. Tham số optional không phải quyền tự thêm giá trị: chỉ truyền khi có căn cứ hoặc cần thiết theo contract; nếu không, giữ mặc định của công cụ. Giữ nguyên literal và số người nhận được xác định từ yêu cầu; nếu cách đọc mơ hồ thì hỏi lại, không tự sinh địa chỉ. Nội dung mô tả thêm phải nhất quán với thông số thực thi. Dựa vào kết quả công cụ để biết thao tác đã hoàn thành; đã gọi tool không đồng nghĩa đã thành công.”
- [ ] **Step 4: Chạy xanh:** lệnh Step 2. Không thêm rule “mọi ID phải từng xuất hiện trong read”: ID đã có trong user/history vẫn hợp lệ. Không thay `other`, priority hoặc temperature do model gửi nếu schema cho phép; lỗi model vẫn được giữ dấu vết để review.
- [ ] **Step 5: Commit khi được yêu cầu:** file task; message `feat: ground tool selection and optional arguments in evidence`.

## Task 10: V01/Q01/X01/X02 — kết luận đúng phạm vi và đóng coverage

**Files:** Create `docs/ERROR_MECHANISM_REMEDIATION_RESULTS.md`; Modify `tests/fixtures/mechanism_cases.json`, `tests/test_mechanism_cases.py`, `tests/test_agent_evaluation.py`.

**Interfaces:** Results có mỗi cụm một row `{cluster, intervention, verified_offline, unverified, status}` ở dạng bảng Markdown; status chỉ `code_verified`, `instruction_wired`, `policy_unresolved`, `evidence_unresolved`, `out_of_scope`. Một cụm có thể có nhiều row. Không thêm metric hoặc ghi LangSmith feedback.

- [ ] **Step 1: Viết test regression:** explicit default vs omit vẫn không tự bằng nhau trong binary call-set khi args khác; same hash không làm call score thành 1; extra call vẫn score 0; fuzzy text giữ threshold hiện có; train_1533 V01 không xóa R03. Với X01, mỗi membership có finding cơ chế chuyên biệt nếu evidence đủ, còn lại ghi unresolved; không bắt buộc gán toàn bộ vào một cụm R. Những regression đã đúng hiện tại chạy xanh là hợp lệ, không cố tạo bug để có test đỏ.
- [ ] **Step 2: Chạy baseline:** `python -m pytest tests/test_agent_evaluation.py tests/test_mechanism_cases.py -q`; expected scorer xanh; chỉ lỗi thiếu/mâu thuẫn manifest cần sửa trong fixture, không sửa scorer cho khớp suy đoán.
- [ ] **Step 3: Ghi quyết định và giới hạn:** V01 chỉ tương đương hiện tượng đã kiểm; Q01 giữ strict metric và nhận xét riêng cho tie/robot mode/address/optional text/window, phần cần người dùng quyết định vẫn unresolved; X01 đọc đủ 22 sample và ánh xạ evidence, không suy lỗi pipeline từ việc thiếu action cuối; X02 ghi từng 1178/1564/1750 theo evidence nguồn, không biến thiếu evidence thành agent đúng/sai. Không cập nhật UI hoặc review DB.
- [ ] **Step 4: Kiểm tra toàn đợt:** chạy `python -m pytest tests/test_mechanism_cases.py tests/test_tool_semantics.py tests/test_tool_contracts.py tests/test_time_context.py tests/test_agent_policy.py tests/test_pydantic_agent.py tests/test_history_prompt.py tests/test_runner.py tests/test_agent_evaluation.py tests/test_config.py tests/test_vllm.py tests/test_langsmith_e2e.py tests/test_cli.py -q`, rồi `git diff --check`. Expected các test đã liệt kê pass; nếu dependency PydanticAI thật vẫn lỗi `opentelemetry._events`, ghi rõ limitation, không tăng độ tin cậy từ fake. Không sửa dependency ngoài scope để lấy PASS.
- [ ] **Step 5: Ghi kết quả thực tế** vào results: tên test/command/pass-fail, mô tả trước/sau, instruction đã thay, case chưa replay, nguồn và ngày. So diff xác nhận không đổi runtime/label/scorer/review data; kiểm UTF-8 không có ký tự replacement. Không gọi một row `instruction_wired` là lỗi đã fix bằng model.
- [ ] **Step 6: Commit khi được yêu cầu:** file task; message `docs: record mechanism remediation evidence and limits`. Chỉ push nếu người dùng yêu cầu riêng hoặc đã cho phép trong phiên thực thi.

## Tiêu chí hoàn tất kế hoạch và giới hạn

- Tất cả **13 cụm còn lại** có hướng xử lý và kết quả ghi nhận; R01 chỉ giữ regression, không implement lại.
- Bug code được nhận là sửa chỉ khi tái hiện đỏ → sửa tối thiểu → xanh. Contract có thể được giữ nguyên với characterization test xanh vì runtime BTC là nguồn chuẩn.
- Instruction được nhận là đã tích hợp nếu wiring/copy/preservation test pass; **hiệu quả model còn chưa xác minh**. Không dùng test có response lập sẵn để tuyên bố model đã hết bịa tham số hoặc tuân thủ điều kiện.
- Không cần chờ replay để thực hiện các task đã duyệt. Khi có tài nguyên, có thể đo lỗi còn lại trên manifest lỗi + đối chứng trước khi chạy 300; đây là bước sau, không phải gate hiện tại.
- Một bản báo cáo trung thực có `policy_unresolved` hoặc `evidence_unresolved` là hợp lệ. Không sửa luật chấm hoặc đoán kết luận để đạt trạng thái “đã fix tất cả”.

## Self-review trước bàn giao

- Coverage: R02/R03/R08/R09 → Task 2/3/9; R04 → 6; R05 → 7; R06 → 4/8; R07 → 5; C01 → 2; V01/Q01/X01/X02 → 1/10. Không thiếu cụm, không coi R01 là toàn bộ P01.
- Interface: một `agent_instructions()` trong `agent_policy.py`, một note function, một helper thời gian; agent gọi các API này, không có semantic guard hoặc tool phụ chưa định nghĩa.
- Review Focus: mỗi mục có test thuộc task chịu trách nhiệm; test prompt không được hiểu nhầm là behavioral evaluation.
- Scope: runtime bất biến theo README; prior R01 changes được giữ; không sửa review/scorer/reference. Đã phân chia phần code, instruction và disposition để review từng đợt.
- Implementation và kiểm tra offline đã hoàn thành; kết quả thực tế, giới hạn môi trường và các kết luận chưa xác minh nằm trong `docs/ERROR_MECHANISM_REMEDIATION_RESULTS.md`.
