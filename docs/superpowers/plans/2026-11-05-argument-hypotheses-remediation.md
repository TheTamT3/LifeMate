# Argument Hypotheses Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xử lý đủ 19 giả thuyết lỗi tham số theo hướng A: thay đổi nhỏ có căn cứ, instruction tổng quát và điều tra riêng nơi chưa đủ bằng chứng; không xây hệ thống quan sát ID trong đợt fixing.

**Architecture:** Giữ vòng lặp agent và official ToolEnv hiện tại. Sửa cách trình bày lịch, làm rõ policy/semantic note. H-ID-ROLE chỉ sửa instruction; không thêm observer, mapping ID hoặc metadata chẩn đoán. Không xây bộ nhớ fact, parser ngôn ngữ, bộ sửa arguments hoặc guard ngữ nghĩa tổng quát.

**Tech Stack:** Python hiện tại của repo, pytest, Pydantic/PydanticAI hiện có, LangSmith E2E tracer hiện có; không thêm dependency.

**Spec:** [Thiết kế hướng A](../specs/2026-11-05-argument-remediation-design.md), [rules](../../REMEDIATION_RULES.md), [19 hướng trong report](../../../review_data/argument_mechanisms_5efb0ae0_20261104/REPORT.md) và `causal_hypotheses.json` cùng thư mục. Spec hướng A thay thế các hướng code rộng của chín mục còn vướng; mười mục còn lại theo report, giới hạn bởi rules. Người dùng yêu cầu viết plan toàn bộ 19 mục; plan này chờ review, không phải lệnh implement.

## Global Constraints

- Giữ giới hạn request hiện tại là 10, quyền quyết định tiếp tục/dừng của agent và cơ chế hỏi đang có.
- Không thêm lượt model, dependency, tool ngoài catalog hoặc model phụ. Không sửa catalog/runtime chính thức, label, trace gốc hay dữ liệu review.
- Không bật lại thinking history; không xây parser giờ, bộ nhớ fact, bộ tự sửa literal hoặc bộ nhận diện dependency tổng quát.
- Không hardcode sample ID/label trong production; sample chỉ dùng làm bằng chứng/test. Không lấy hidden state làm dữ kiện agent.
- Task 6–8 chuyển sang backlog điều tra theo quyết định của người dùng. Không tạo observer, mapping ID, cờ observe_id_sources, hook hoặc metadata chẩn đoán trong đợt này; không chặn call hoặc tự sửa arguments/kết quả.
- Không replay LLM, không khởi động server, không phát request ra LangSmith thật trong đợt offline này. Mọi HTTP của integration test phải được mock.
- Không cập nhật `solution_review.json`: H-DATE-MEM/H-CLOCK-PARSE cũ vẫn disagreed; không đổi thành agreed vì đang thử hướng instruction thay thế.
- Tách commit theo task khi thực thi plan được duyệt; không push nếu chưa được yêu cầu. Khi viết plan này không commit/push hoặc sửa production.
- Không tuyên bố model hết lỗi hoặc đạt dưới 30 giây chỉ từ kiểm tra offline. Request limit 10 không phải timeout 30 giây.
- P01/R01 dừng sớm đã sửa: chỉ chạy regression phù hợp, không mở lại thiết kế dừng sau write.

## Review Focus

- Cùng chuỗi ID hợp lệ ở nhiều loại đối tượng hoặc có alias: instruction không được cấm dùng ID qua app một cách tuyệt đối; Task 3 giữ đối chứng contacts→sms hợp lệ trong ma trận đánh giá.
- User sửa yêu cầu, không ghi buổi nhưng context đủ, hoặc ủy quyền lựa chọn: policy không được bám fact cũ hoặc hỏi thừa; Task 2–3 thêm đối chứng vào ma trận đánh giá, chỉ wiring được kiểm offline.
- Mốc qua ngày/tháng/năm và offset khác ngày UTC: Task 1 kiểm lịch theo context, đủ 14 ngày, không dùng host clock.
- Tool trả done=false hoặc ném lỗi: giữ nguyên xử lý và call/result; Task 4 và 10 chạy regression hiện có, không thêm wrapper hoặc tự retry write.
- Cùng response có call phụ thuộc và call độc lập: Task 4 giữ quyền multi-call và regression số call/thứ tự; không coi fixture scripted là bằng chứng model tuân thủ instruction.

---

## Scope và bảng bao phủ

Đây là plan cho **19 giả thuyết của 14 cơ chế trong report ARG**, không phải viết lại toàn bộ 48 mã phân nhóm lịch sử hay plan R01–R09 cũ. Các phần cùng một pipeline và policy nên giữ một plan có task riêng để review/hoàn tác độc lập.

| Giả thuyết | Deliverable của đợt này | Task | Phần hoãn |
| --- | --- | --- | --- |
| H-DATE-ISO | Tên thứ tiếng Việt từ lịch chuẩn | 1 | Hiệu quả model chưa đo |
| H-DATE-MEM | Instruction đối chiếu ngày còn hiệu lực | 2 | Fact memory, giữ thinking |
| H-CLOCK-PARSE | Instruction quy đổi đủ giờ/phút/buổi | 2 | Parser tiếng Việt |
| H-ANCHOR-ROLE | Instruction phân biệt vai trò mốc | 2 | Helper tự chọn/tính từ mốc suy đoán |
| H-ANCHOR-MARGIN | Instruction không tự thêm buffer, không đổi deadline | 2 | Guard sửa giờ |
| H-ID-ROLE | Chỉ sửa instruction dùng đúng loại ID và nguồn tra cứu | 3 | Task 6–8 observer/hook/metadata; guard chặn ID |
| H-ID-OPTIONAL | Semantic note get_ride | 5 | Tự chọn/hủy chuyến |
| H-AMBIG-ORDER | Instruction chọn theo căn cứ, giữ ngoại lệ ủy quyền | 3 | Code chọn ứng viên |
| H-MISSING-EXAMPLE | Audit ví dụ/default/enum có trích nguồn | 9 | Thay số ví dụ tự động |
| H-MISSING-COMMIT | Instruction không hành động bằng giá trị đã biết còn thiếu | 3 | Guard known/unknown |
| H-LITERAL-REGEN | Instruction giữ chuỗi đã xác định | 3 | Parser/chuẩn hóa/sửa call |
| H-DIMENSION-SLOT | Instruction phân biệt đơn vị và đại lượng | 3 | Guard đơn vị, calculator mới |
| H-ENTITY-ATTRIBUTE | Instruction giữ tiêu chí nhận diện đúng vai trò | 3 | Fuzzy matching chọn ID |
| H-CONSTRAINT-CONTRACT | Semantic note thanh toán toàn bộ từ một source | 5 | Tự đổi nguồn tiền |
| H-ENCODE-BOUNDARY | Audit dữ liệu raw trước/sau server parser | 9 | Sửa generation/parser khi chưa có bằng chứng |
| H-CONTENT-DEPEND | Instruction chờ return trước khi soạn call phụ thuộc | 4 | Dependency engine/cấm multi-call |
| H-CONTENT-REWRITE | Instruction giữ fact khi viết lại nội dung | 3 | So khớp body với reference |
| H-DEFAULT-AUTHORITY | Policy mặc định có ngoại lệ user giao quyền | 3 | Code tự bỏ priority |
| H-INTERVAL-SEMANTICS | Semantic note partial update | 5 | Guard interval, end=start+1h |

“Xử lý đủ” nghĩa là mỗi mục có deliverable và giới hạn được ghi nhận; không nghĩa là cả 19 nguyên nhân đã xác nhận hoặc mọi mục đều phải sửa production.

Cập nhật sau review: giữ số task để đối chiếu hội thoại; **Task 1–5 và 10 là phần fixing/kiểm chứng, Task 9 là điều tra, Task 6–8 là backlog chưa triển khai**. Không tính hạ tầng quan sát là bản fix model.

## File structure và trách nhiệm

| File | Trách nhiệm |
| --- | --- |
| `src/lifemate/time_context.py` | Lịch chỉ suy ra từ current_time |
| `src/lifemate/agent_policy.py` | Policy tổng quát, giữ API `agent_instructions() -> str` |
| `src/lifemate/tool_semantics.py` | Bổ sung mô tả đúng contract cho ba tool |
| `tests/test_time_context.py`, `tests/test_history_prompt.py` | Lịch và dynamic prompt |
| `tests/test_agent_policy.py`, `tests/test_tool_semantics.py` | Wiring policy/description, tính nguyên vẹn input/schema |
| `tests/test_pydantic_agent.py`, `tests/test_runner.py`, `tests/test_langsmith_e2e.py` | Chạy regression hiện có; không thêm hook observer |
| `docs/ARGUMENT_REMEDIATION_EVALUATION.md` (mới) | Ma trận 19 mục, đối chứng và phần chưa đo |
| `docs/ARGUMENT_REMEDIATION_AUDIT.md` (mới) | Bằng chứng contract, audit ví dụ/server boundary |
| `docs/ARGUMENT_REMEDIATION_STATUS.md` (mới) | Commit/checks/scope/rollback và trạng thái cuối đợt |

Không tạo module production mới. Không sửa `pydantic_agent.py`, `runner.py`, smoke CLI hoặc tracer để phục vụ quan sát ID. Không dùng `tests/test_tracing.py` làm đường tích hợp chính: file này tham chiếu `lifemate.tracing` hiện không có trong tree; tracer E2E đang dùng là `src/lifemate/langsmith_e2e.py`.

## Chuẩn bị và baseline khi thực thi

- [ ] Đọc spec/rules/report, kiểm `git status --short`; tạo worktree khi cần theo skill thực thi, không ghi đè thay đổi của user.
- [ ] Trong PowerShell đặt `$env:PYTHONPATH='src'` và `$env:PYTHONIOENCODING='utf-8'`. Dùng `apply_patch` cho tiếng Việt; không pipe source Unicode từ PowerShell sang Python.
- [ ] Chạy baseline: `python -m pytest tests/test_time_context.py tests/test_history_prompt.py tests/test_agent_policy.py tests/test_tool_semantics.py tests/test_pydantic_agent.py tests/test_runner.py tests/test_langsmith_e2e.py -q`.
- [ ] Ghi lỗi có sẵn vào STATUS cùng command. Thiếu dependency hoặc API incompatibility không tự sửa pin trong đợt này; tách baseline failure khỏi regression, không tuyên bố tất cả pass.

### Task 1: Lịch dùng tên thứ rõ ràng — H-DATE-ISO

**Files:** Modify `src/lifemate/time_context.py:build_time_context`, `tests/test_time_context.py`, `tests/test_history_prompt.py`; Create `docs/ARGUMENT_REMEDIATION_EVALUATION.md`.

**Interfaces:** Giữ `build_time_context(context: dict[str, Any]) -> dict[str, Any]`; dòng calendar đổi thành `{'date': str, 'weekday_vi': str}`. Khóa anchor/today/tomorrow/day_after_tomorrow và kiểu lỗi giữ nguyên. Runner không đổi API.

- [ ] **Step 1: Viết/đổi test lịch trước.** Trong `test_calendar_uses_sample_time_and_current_and_next_week`, assert dòng đầu `{'date': '2026-11-02', 'weekday_vi': 'thứ hai'}`, dòng cuối `{'date': '2026-11-15', 'weekday_vi': 'chủ nhật'}` và len=14. Thêm `test_calendar_has_all_vietnamese_weekdays_without_iso_numbers` kiểm tuần đầu bằng đúng `['thứ hai','thứ ba','thứ tư','thứ năm','thứ sáu','thứ bảy','chủ nhật']` và không còn khóa iso_weekday.
- [ ] **Step 2: Chạy red.** `python -m pytest tests/test_time_context.py -q`; fail phải do weekday_vi chưa có, không do import.
- [ ] **Step 3: Sửa tối thiểu `build_time_context`.** Tuple tên thứ cố định, index bằng `.weekday()`; giữ phép tính ngày/phạm vi và điều kiện current_time hợp lệ. Không dùng host date hoặc cộng/trừ để sửa mẫu lỗi.
- [ ] **Step 4: Bổ sung test boundary/integration.** Giữ invalid/naive→{}, offset +14:00. Test anchor `2028-02-29T23:30:00+07:00` cho tomorrow 2028-03-01, anchor 2026-12-31 cho tomorrow 2027-01-01. Trong history prompt test parse JSON calendar thật, không chỉ tìm substring; assert context và user text không bị sửa.
- [ ] **Step 5: Chạy green.** `python -m pytest tests/test_time_context.py tests/test_history_prompt.py -q`.
- [ ] **Step 6: Ghi phần DATE-ISO trong EVALUATION.** Có lỗi đã thấy, case đang đúng và boundary chưa dùng thiết kế; phân biệt unit correctness với model accuracy. Commit `fix: present calendar weekdays in Vietnamese` với đúng file task.

### Task 2: Policy thời gian — bốn giả thuyết DATE/CLOCK/ANCHOR

**Files:** Modify `src/lifemate/agent_policy.py:TIME_POLICY`, `tests/test_agent_policy.py`; Extend EVALUATION.

**Interfaces:** Giữ tất cả constant public hiện có và `agent_instructions() -> str`; tích hợp trong TIME_POLICY, không thêm model request/helper/parser.

- [ ] **Step 1: Đọc policy hiện tại và đánh dấu câu cần thay.** Bảo toàn context authority, timezone, ngày rõ ràng và quyền hỏi khi mơ hồ. Nội dung DATE-MEM/CLOCK-PARSE/ANCHOR-ROLE theo spec §4; thêm ANCHOR-MARGIN theo report: đúng lúc thì giữ đúng lúc, offset chỉ theo yêu cầu, deadline không biến thành giờ tự chọn. Cho phép khoảng đệm/giờ do user đã giao quyền chọn.
- [ ] **Step 2: Tích hợp instruction ngắn, giữ thứ tự policy.** Không thêm test chỉ khớp từng câu tiếng Việt mới; không dùng test đó để suy ra model hành xử đúng.
- [ ] **Step 3: Chạy integration có sẵn.** `python -m pytest tests/test_agent_policy.py tests/test_history_prompt.py -q`; kiểm static policy được truyền đúng một lần, dynamic context riêng, request/history không bị rewrite. Chỉ sửa assertion gắn với lời cũ nếu ý nghĩa vẫn được bảo toàn.
- [ ] **Step 4: Thêm ma trận đánh giá cho cả bốn mục.** Mỗi mục có observed_error, valid_control, novel_variant. Bắt buộc gồm user đổi ngày sau retry; “6 rưỡi” có context buổi đủ/thiếu; giờ hẹn khác giờ xe; nhiều mốc cập nhật; nhắc đúng 15:00 so với user yêu cầu trước 10 phút; deadline 17:00 không tự chọn 14:00. Viết điều kiện chấp nhận bằng nghĩa, không bắt nội dung reasoning hoặc chuỗi tool duy nhất.
- [ ] **Step 5: Review đối chiếu rules, commit** `fix: clarify temporal grounding and reminder authority`. Đây là thay đổi instruction; không viết scripted-model test rồi gọi đó là bằng chứng hết lỗi ngày/giờ.

### Task 3: Policy chọn đối tượng, dữ kiện và nội dung — tám giả thuyết

**Files:** Modify `src/lifemate/agent_policy.py:BASE_POLICY,EVIDENCE_POLICY`, `tests/test_agent_policy.py`; Extend EVALUATION.

**Interfaces:** Giữ API policy; dùng đúng policy đang compose, không thêm fact store, bước model phụ hay tool mới. Bao phủ H-ID-ROLE, H-AMBIG-ORDER, H-MISSING-COMMIT, H-LITERAL-REGEN, H-DIMENSION-SLOT, H-ENTITY-ATTRIBUTE, H-CONTENT-REWRITE, H-DEFAULT-AUTHORITY.

- [ ] **Step 1: Soạn diff thay câu liên quan, không chỉ append.** Nội dung bắt buộc: ID đúng loại đối tượng; chọn theo tiêu chí nhận diện, không mặc định theo thứ tự; nhiều ứng viên nhưng đã được phép chọn tùy ý không bị buộc hỏi; thiếu dữ kiện cần thiết thì tra/hỏi, phép tính có căn cứ vẫn hợp lệ; giữ literal/số đầu 0/số lặp; phân biệt số lượng/đơn vị/đơn giá/tổng; giữ fact khi diễn đạt lại; default có ngoại lệ giao quyền như spec §4. Không ghi tên app/sample vào policy tổng quát.
- [ ] **Step 2: Giải quyết xung đột hiện có.** Câu hiện tại “còn nhiều ứng viên phù hợp, hỏi” phải có ngoại lệ tiêu chí duy nhất/ủy quyền; câu optional phải bảo toàn lựa chọn cần thiết theo contract và user giao quyền. Không map “gấp” cứng sang high; không biến mọi giá trị suy ra thành thiếu căn cứ.
- [ ] **Step 3: Kiểm wiring và dữ liệu nguyên vẹn.** Chạy `python -m pytest tests/test_agent_policy.py tests/test_history_prompt.py tests/test_tool_semantics.py -q`. Giữ `test_build_agent_uses_composed_policy`, kiểm không nhúng sample ID và user/history literal không đổi. Không thêm test dự đoán lựa chọn thật của model bằng fake agent.
- [ ] **Step 4: Mở rộng ma trận cho tám mục.** Bắt buộc: đảo thứ tự ứng viên; user chọn tùy ý; cùng tên khác vai trò; ID contacts dùng hợp lệ qua sms; ID ngân hàng khác ID contact; amount tính từ dữ kiện; amount thiếu; số 11 chữ số/email có ký tự hợp lệ; quantity khác chiều dài; tên trong body khác tên nhận chỉ khi user thực sự muốn nhắc người thứ ba; priority do user yêu cầu/ủy quyền/không đề cập.
- [ ] **Step 5: Review tính tổng quát và commit** `fix: clarify entity selection and evidence handling`. Nếu diff quá rộng, có thể chia commit trong task theo selection và value/content; không đưa parser/guard vào.

### Task 4: Chờ dữ kiện phụ thuộc, giữ multi-call hợp lệ — H-CONTENT-DEPEND

**Files:** Modify `src/lifemate/agent_policy.py:CONDITION_POLICY,EVIDENCE_POLICY`; Extend EVALUATION.

**Interfaces:** Không đổi `run_agent`, request_limit, `Tool.from_schema(sequential=True)` hoặc cách pause. Instruction theo spec §4: phân biệt thứ tự thực thi với thời điểm model soạn arguments.

- [ ] **Step 1: Sửa câu chờ kết quả hiện tại.** Nêu rõ khi arguments/nội dung cần dữ kiện mới do call trước tạo ra thì chờ return rồi mới tạo call sau; call độc lập vẫn được tạo cùng response. Không hardcode “chuyển khoản → SMS”, không ép tất cả chỉ một tool mỗi lượt.
- [ ] **Step 2: Chạy regression vòng lặp có sẵn.** `python -m pytest tests/test_pydantic_agent.py tests/test_agent_policy.py -q`; đặc biệt giữ `test_iter_runner_preserves_same_response_calls_and_stops_for_user`, `test_iter_keeps_usage_limit_error_without_synthetic_calls` và test write tiếp tục. Không thay scripted call thành bằng chứng model chọn dependency đúng.
- [ ] **Step 3: Thêm đối chứng vào EVALUATION.** Receipt cần mã mới; write done=false không được báo thành công; dữ kiện đã có từ history; hai write độc lập; nội dung chỉ trích dẫn “nếu…” không phải điều kiện thực thi.
- [ ] **Step 4: Commit** `fix: clarify data dependencies between generated tool calls`.

### Task 5: Semantic note từ contract — ba giả thuyết

**Files:** Modify `src/lifemate/tool_semantics.py:_NOTES`, `tests/test_tool_semantics.py`; Create `docs/ARGUMENT_REMEDIATION_AUDIT.md`; Extend EVALUATION.

**Interfaces:** Giữ `tool_semantics_note(name: str) -> str`; unknown trả ''. Không đổi schema hoặc official ToolEnv.

- [ ] **Step 1: Viết failing tests `test_argument_semantics_overlays_do_not_mutate_schemas_or_execution`.** Parametrize ba official tool. Dùng `FakeTool.from_schema` hiện có để lấy description và invoke; so sánh deep copy catalog trước/sau, json_schema trước/sau note giống nhau, env nhận đúng arguments và chỉ gọi một lần, result giữ nguyên.
- [ ] **Step 2: Chạy red.** `python -m pytest tests/test_tool_semantics.py -q`; thiếu note là lý do fail.
- [ ] **Step 3: Thêm/ghép ba note.** `ride_hailing.get_ride`: bỏ ride_id trả chuyến hiện tại, có ID tra chuyến đó; không tự hủy. `bill_payment.pay`: thanh toán toàn bộ hóa đơn từ một source, không hỗ trợ partial/split trong call. `calendar.update_event`: giữ note không tự khôi phục cancelled; thêm omitted field giữ nguyên, end không tự dịch, tính cả end khi yêu cầu giữ thời lượng và lịch cũ đã biết.
- [ ] **Step 4: Ghi nguồn contract vào AUDIT.** Trích đường dẫn/hàm `apps/ride_hailing.py:get_ride`, `bill_payment.py:pay`, `calendar.py:update_event`, `base.py:patch`, schema trong catalog. Không chạy ToolEnv thật vào sample chỉ để chứng minh contract.
- [ ] **Step 5: Chạy green.** `python -m pytest tests/test_tool_semantics.py tests/test_pydantic_agent.py -q`. EVALUATION thêm get_ride không ID trả no-op; chuyến không khớp yêu cầu; wallet đủ/thiếu/không được fallback; event 30 phút/qua nửa đêm/title-only/đổi duration.
- [ ] **Step 6: Commit** `fix: document ride lookup payment and calendar update semantics`.

### Task 6–8: Backlog điều tra nguồn ID — chưa triển khai

| Task cũ | Ý tưởng giữ trong backlog | Trạng thái |
| --- | --- | --- |
| 6 | Bộ ghi nhận nguồn/loại ID từ tool-return | Hoãn; không tạo module, mapping hoặc test observer |
| 7 | Hook bộ ghi nhận vào pipeline | Hoãn; không đổi AgentDependencies hoặc run_sample |
| 8 | Đưa quan sát lên trace metadata | Hoãn; không thêm CLI flag hoặc metadata |

Ba mục này chỉ hỗ trợ điều tra, không trực tiếp làm agent chọn đúng ID. Người dùng đã đồng ý chuyển sang backlog; không có bước implementation/commit cho chúng trong đợt fixing. Chỉ xem xét lại khi có yêu cầu điều tra riêng. H-ID-ROLE vẫn được xử lý bằng instruction tại Task 3; chưa xác nhận hiệu quả bằng replay.

### Task 9: Hai hướng điều tra, không ép thành production fix

**Files:** Extend `docs/ARGUMENT_REMEDIATION_AUDIT.md`, EVALUATION; không sửa raw report/hypotheses hoặc server config.

**Interfaces:** AUDIT có hai bảng schema cố định bên dưới. Đây là tác vụ tài liệu/read-only: không viết test chỉ để kiểm nội dung Markdown và không tự chạy LLM.

- [ ] **Step 1: Audit H-MISSING-EXAMPLE.** Đọc catalog/description model-facing của các probe liên quan trong report, đối chiếu schema/runtime. Bảng gồm `tool.parameter | source path | exact description | example/default/enum-or-bound | ambiguity | proposed clarification | production change status`. Không coi default/enum là ví dụ hoặc tự xóa số. Mỗi nhận định phải có nguồn; không có nhập nhằng thì kết luận no change, hypothesis unconfirmed.
- [ ] **Step 2: Audit H-ENCODE-BOUNDARY.** Kiểm artifacts local đã có bằng `rg --files logs review_data`; không đọc credential hay gọi server. Bảng gồm `request/call identity | request input | raw pre-parser generation | post-parser response | client response | comparable boundaries | conclusion`. Chỉ gọi raw khi đúng trước parser; trace client không tự nâng thành raw token stream.
- [ ] **Step 3: Nếu thiếu raw lịch sử, ghi blocked evidence thay vì tự chọn fix.** Mô tả dữ liệu cần thu khi có server và được phép, cùng request/call ID; không cài logger server, sửa sampling/parser hay ép car4 ở đợt này. Nếu có raw thì so sánh read-only, đề xuất fix tiếp theo riêng để review.
- [ ] **Step 4: Cập nhật EVALUATION cho hai mục và commit** `docs: audit schema examples and tool parsing evidence`. Không đổi hai giả thuyết thành confirmed chỉ vì hoàn tất audit.

### Task 10: Kiểm chứng tích hợp, bàn giao và rollback

**Files:** Create/Finalize `docs/ARGUMENT_REMEDIATION_STATUS.md`; Finalize EVALUATION và AUDIT; không sửa file reviewer quyết định.

**Interfaces:** EVALUATION có đúng 19 mã. Mỗi mã gồm `change_type`, `observed_error`, `valid_control`, `novel_variant`, `acceptance_by_meaning`, `offline_evidence`, `model_evidence`, `deferred`. STATUS ánh xạ mã→task→commit→commands→actual result; tách “implemented/observed/deferred” khỏi “model fix confirmed”. Các mẫu gốc giữ nguyên file nguồn, chỉ tham chiếu.

- [ ] **Step 1: Self-review coverage.** Đối chiếu 19 IDs với `causal_hypotheses.json`, không bỏ mã, không thêm cách sửa đã hoãn. Mỗi mục có valid_control và novel_variant, mọi chỗ chưa có model evidence ghi “chưa replay”. Kiểm instruction không lặp/mâu thuẫn và không thêm tên app/sample vào policy tổng quát.
- [ ] **Step 2: Chạy suite liên quan.** `python -m pytest tests/test_time_context.py tests/test_history_prompt.py tests/test_agent_policy.py tests/test_tool_semantics.py tests/test_pydantic_agent.py tests/test_runner.py tests/test_langsmith_e2e.py tests/test_config.py tests/test_vllm.py tests/test_cli.py -q`. Chỉ yêu cầu green đối với baseline hỗ trợ; mọi baseline failure phải có bằng chứng trước/sau, không âm thầm skip để báo pass.
- [ ] **Step 3: Kiểm diff và dữ liệu.** `git diff --check`; inspect diff catalog/runtime/labels/solution_review.json phải không có thay đổi do đợt này. Output giữ đúng schema submission. Kiểm không có code truy cập sample ID/reference/hidden state trong policy/calendar và không thêm model request, observer, mapping ID hoặc hook/metadata.
- [ ] **Step 4: Ghi rollback riêng.** Calendar revert commit Task 1; các policy revert từng commit Task 2–4, semantics Task 5. Dùng commit của đợt này, không dùng reset/restore phá thay đổi khác của user. Không tự rollback khi chưa có chỉ dẫn hoặc regression cần xử lý trong scope.
- [ ] **Step 5: Ghi kết quả thật, commit** `docs: record argument remediation validation and limits`. Không ghi sẵn số pass dự kiến thành số thực tế. Báo rõ chưa xác nhận accuracy, latency dưới 30 giây hoặc zero regression của model; audit/diagnostics không được tính là case đã fix.

## Bàn giao sau plan

Sau khi người dùng review plan và chọn cách thực thi, dùng skill tương ứng ở header. Đề xuất **Native** vì các thay đổi policy dùng chung file và phạm vi code đã thu hẹp; kiểm độc lập ở cuối khi được chọn, không cần nhiều agent sửa cùng file. Không bắt đầu implement chỉ vì plan đã được viết hoặc người dùng đồng ý chuyển Task 6–8 sang backlog.

## Self-review của bản plan

- Bao phủ: bảng scope có đúng 19 mã, Task 1–5 và 9 có deliverable cho từng mã; Task 10 kiểm toàn đợt. Task 6–8 là backlog, không coi mục hoãn/điều tra là đã sửa nguyên nhân.
- Chữ ký: giữ nguyên runner/agent/tracer và submission result; không thêm module hoặc mapping ID, không thêm field vào official schema.
- Review Focus: lịch có boundary test; ID qua app hợp lệ, quyền ủy quyền/thời gian mơ hồ có ma trận đánh giá nhưng hiệu quả model chưa kiểm offline; regression vòng lặp/tool failure vẫn chạy.
- Mức độ test: logic mới có red/green; instruction dùng wiring hiện có và review nghĩa/đối chứng, không tạo test keyword để giả vờ chứng minh model đúng; audit Markdown không thêm test implementation-mirroring.
- Giới hạn: không replay/network, không sửa dependencies để che baseline, không cập nhật trạng thái duyệt cũ; hai hướng code bị từ chối tiếp tục hoãn.
