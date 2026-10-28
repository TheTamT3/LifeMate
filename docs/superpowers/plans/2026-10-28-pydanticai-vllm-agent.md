# PydanticAI + vLLM Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển baseline sang PydanticAI thực sự, dùng `Qwen/Qwen3-4B` được vLLM phục vụ tại endpoint local để điều phối tool calling qua `ToolEnv`.

**Architecture:** Một lớp cấu hình/model factory chỉ cho phép endpoint loopback và tạo PydanticAI OpenAI-compatible model. Factory tool chuyển từng tool được lọc từ catalog thành PydanticAI tool động, có wrapper gọi `ToolEnv`. Runner tạo agent riêng cho mỗi sample và chỉ lấy `tool_calls`/`state_hash` từ environment sau khi agent kết thúc.

**Tech Stack:** Python 3.10+, PydanticAI 1.16.0, OpenAI-compatible provider, vLLM, Qwen/Qwen3-4B, Pydantic v2, pytest, zaic_tools.

**Spec:** `docs/superpowers/specs/2026-10-28-vllm-pydanticai-agent-design.md`

## Global Constraints

- Dùng checkpoint `Qwen/Qwen3-4B`; LLM dưới 5B tham số, context không quá 16.384 token.
- vLLM chạy hoàn toàn offline tại `localhost`/`127.0.0.1`; CLI phải từ chối endpoint từ xa.
- Suy luận có thể tái lập: `temperature=0`, `top_p=1`, seed cố định.
- Tạo đúng một `ToolEnv` mỗi sample; không đọc, parse hay sao chép file trong `<split>_environment/`, gồm `state.json`.
- Chỉ đăng ký tool thuộc `context.installed_apps`, cùng system tool `sys.ask_missing_info` khi catalog cung cấp; giữ nguyên tên chính thức, mô tả và JSON Schema từ catalog.
- `kind == "read"` là điều kiện duy nhất cho phép sang lượt tool tiếp theo; dừng sau `write`, `meta`, không call, lỗi hoặc 8 lượt.
- Submission chỉ gồm `id`, `env.get_tool_calls()` và `env.get_state_hash()`; không dựng lại calls/hash trong agent.
- Không thay ASR, cách đọc JSONL, format output UTF-8, few-shot, fine-tune/LoRA hoặc Docker trong phạm vi kế hoạch này.
- vLLM chỉ là dependency của Linux/Colab serving environment, không bắt buộc cài trên Windows RTX 3050 4 GB.

## Review Focus

- Endpoint `https://...` hoặc IP không phải loopback phải bị từ chối trước khi tạo client — Task 1.
- Tool có trong catalog nhưng không thuộc `installed_apps` không được xuất hiện trong tool definitions và không thể gọi `ToolEnv` — Task 2.
- Schema có `required`, `enum`, giới hạn số và `x-one-of` phải chặn arguments sai trước `ToolEnv` — Task 2.
- Lượt có `write` hoặc `meta` phải không tạo thêm model round, nhưng các calls cùng response hợp lệ vẫn được ghi theo thứ tự — Task 3.
- Model/service lỗi, output không có tool call, hoặc schema validation thất bại phải không tạo call tự chế và output cuối vẫn lấy từ environment — Task 4.

---

## Cấu trúc file

- `src/lifemate/vllm.py`: cấu hình endpoint/model, kiểm tra loopback và tạo PydanticAI model client.
- `src/lifemate/pydantic_agent.py`: dependencies theo sample, system prompt, tool factory từ catalog và hàm chạy agent.
- `src/lifemate/runner.py`: tích hợp agent mới với `ToolEnv`; bỏ raw JSON parsing khỏi đường chạy chính.
- `src/lifemate/cli.py`: thêm các tuỳ chọn vLLM và truyền cấu hình vào runner.
- `requirements.txt`: pin PydanticAI với OpenAI provider; bổ sung ghi chú dependency vLLM cho Linux/Colab.
- `RUNBOOK.md`: lệnh khởi động vLLM offline và chạy baseline qua endpoint local.
- `tests/test_vllm.py`, `tests/test_pydantic_agent.py`: test thuần CPU/mock cho endpoint và tool factory/orchestration.
- `tests/test_runner.py`, `tests/test_cli.py`, `tests/test_integration.py`: cập nhật các contract hiện hữu.

### Task 1: Thêm cấu hình vLLM local và PydanticAI model factory

**Files:**
- Create: `src/lifemate/vllm.py`
- Modify: `src/lifemate/config.py`
- Modify: `requirements.txt`
- Create: `tests/test_vllm.py`

**Interfaces:**
- Produces `VLLMConfig(base_url: str = "http://127.0.0.1:8000/v1", model_name: str = "qwen3-4b", max_steps: int = 8)`.
- Produces `validate_loopback_url(base_url: str) -> str`.
- Produces `create_vllm_model(config: VLLMConfig) -> Any`, returning the public PydanticAI OpenAI-compatible model type.

- [ ] **Step 1: Write failing endpoint tests** in `tests/test_vllm.py`.

```python
def test_loopback_endpoint_is_accepted():
    assert validate_loopback_url("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"

def test_remote_endpoint_is_rejected():
    with pytest.raises(ValueError, match="loopback"):
        validate_loopback_url("https://api.example.com/v1")
```

- [ ] **Step 2: Run the endpoint tests to verify failure.**

Run: `pytest tests/test_vllm.py -v`

Expected: FAIL because `lifemate.vllm` does not exist.

- [ ] **Step 3: Add `VLLMConfig`, `validate_loopback_url()` and `create_vllm_model()` in `src/lifemate/vllm.py`.**

Use URL parsing, accept only `localhost`, `127.0.0.1` and `::1`; normalize no other host. Configure the PydanticAI OpenAI-compatible provider with the supplied model alias and a local base URL. Do not probe network availability here.

- [ ] **Step 4: Extend `RuntimeConfig` in `src/lifemate/config.py` with `llm_base_url`, `llm_model_name` and `max_steps`, retaining the current defaults for unrelated ASR/model fields.**

- [ ] **Step 5: Pin the PydanticAI OpenAI provider dependency in `requirements.txt`.**

Keep vLLM out of the Windows baseline dependencies; document it as a Linux/Colab-only installation requirement in a comment.

- [ ] **Step 6: Run tests to verify success.**

Run: `pytest tests/test_vllm.py tests/test_config.py -v`

Expected: PASS.

- [ ] **Step 7: Commit the configuration boundary.**

```bash
git add requirements.txt src/lifemate/config.py src/lifemate/vllm.py tests/test_vllm.py tests/test_config.py
git commit -m "feat: add local vllm configuration"
```

### Task 2: Tạo dynamic PydanticAI tools từ catalog đã lọc

**Files:**
- Create: `src/lifemate/pydantic_agent.py`
- Create: `tests/test_pydantic_agent.py`
- Modify: `src/lifemate/data.py` only if a public typed catalog helper is needed

**Interfaces:**
- Produces `AgentDependencies(env: Any, tools_by_name: dict[str, dict[str, Any]], max_steps: int)`.
- Produces `build_tool_definitions(deps: AgentDependencies) -> list[Any]`, returning public PydanticAI tool objects.
- Produces `catalog_argument_model(tool: dict[str, Any]) -> type[BaseModel]`.
- Produces `build_agent(model: Any, deps: AgentDependencies) -> Any`.

- [ ] **Step 1: Write failing tool-definition tests** in `tests/test_pydantic_agent.py`.

```python
def test_tool_factory_keeps_official_name_and_validates_arguments(fake_env):
    tool = {"name": "weather.get_current", "kind": "read", "description": "...", "parameters": {
        "type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]
    }}
    definitions = build_tool_definitions(AgentDependencies(fake_env, {tool["name"]: tool}, 8))
    assert len(definitions) == 1
    assert definitions[0].name != "weather.get_current"  # Python-safe internal name
    assert definitions[0].description == tool["description"]
```

Add separate tests that a catalog tool outside `installed_apps` is absent because the caller supplies only `allowed_tools()`, and that missing required values, invalid enum/range and unsatisfied `x-one-of` are rejected without `fake_env.call()`.

- [ ] **Step 2: Run the tool tests to verify failure.**

Run: `pytest tests/test_pydantic_agent.py -v`

Expected: FAIL because the factory does not exist.

- [ ] **Step 3: Implement `catalog_argument_model()` in `src/lifemate/pydantic_agent.py`.**

Support catalog object roots, primitive types, arrays, `required`, `enum`, `minimum`, `exclusiveMinimum`, `format` and `x-one-of`. Preserve `x-ref`/`x-match` as descriptions for the model. Raise a clear development-time error for schema constructs outside this observed catalog profile.

- [ ] **Step 4: Implement `AgentDependencies` and `build_tool_definitions()`.**

Generate a unique Python-safe internal function/tool name for PydanticAI while retaining the catalog's dotted name in closure state. Validate args via the generated model, invoke `deps.env.call(official_name, arguments)`, and return only JSON-safe result data. Record each successful wrapper invocation in dependency state for round-policy tests.

- [ ] **Step 5: Implement `build_agent()` with system instructions that include transcript/context at run time, only registered tools, no invented IDs and no-action behavior.**

Use only public PydanticAI APIs compatible with the pinned version. Do not retain model messages, label or app state in dependencies.

- [ ] **Step 6: Run tests to verify success.**

Run: `pytest tests/test_pydantic_agent.py tests/test_data.py -v`

Expected: PASS.

- [ ] **Step 7: Commit the dynamic tool layer.**

```bash
git add src/lifemate/pydantic_agent.py src/lifemate/data.py tests/test_pydantic_agent.py tests/test_data.py
git commit -m "feat: add catalog-driven pydantic tools"
```

### Task 3: Thêm vòng chạy PydanticAI có giới hạn multi-step

**Files:**
- Modify: `src/lifemate/pydantic_agent.py`
- Modify: `tests/test_pydantic_agent.py`

**Interfaces:**
- Produces `run_agent(agent: Any, deps: AgentDependencies, prompt: str) -> None`.
- Consumes `AgentDependencies`, tool definitions and PydanticAI model created by Tasks 1–2.

- [ ] **Step 1: Write failing orchestration tests using a fake PydanticAI model/tool-call sequence.**

```python
def test_read_result_allows_next_round_then_write_stops(fake_agent, deps):
    run_agent(fake_agent, deps, "request")
    assert deps.env.calls == [
        ("contacts.search", {"query": "An"}),
        ("sms.send", {"contact_id": "c_1", "content": "..."}),
    ]
    assert fake_agent.request_count == 2
```

Add tests for no tool call (zero environment calls), `meta` stopping the next round, the 8-round cap, and invalid argument validation preventing the environment call.

- [ ] **Step 2: Run the orchestration tests to verify failure.**

Run: `pytest tests/test_pydantic_agent.py -v`

Expected: FAIL because `run_agent()` does not exist.

- [ ] **Step 3: Implement `run_agent()` with the public PydanticAI iteration/run API.**

Bound model requests to eight tool-call rounds. Permit a subsequent model turn only if all calls in the prior round have catalog kind `read`; call batches received in a single valid model response retain their order. Stop cleanly on `write`, `meta`, no call, validation failure or provider error. Use `temperature=0` and `top_p=1` in model settings.

- [ ] **Step 4: Run the focused tests to verify success.**

Run: `pytest tests/test_pydantic_agent.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the orchestration policy.**

```bash
git add src/lifemate/pydantic_agent.py tests/test_pydantic_agent.py
git commit -m "feat: orchestrate multistep pydantic tool calls"
```

### Task 4: Chuyển runner sang agent mới và giữ output ToolEnv

**Files:**
- Modify: `src/lifemate/runner.py`
- Modify: `src/lifemate/llm.py`
- Modify: `tests/test_runner.py`
- Modify: `tests/test_integration.py`
- Deprecate: `src/lifemate/agent_schema.py` and `src/lifemate/prompting.py` only after all callers are removed

**Interfaces:**
- Changes `run_sample(sample, split, root, catalog, llm_model, asr=None, max_steps=8) -> dict[str, Any]` to consume a PydanticAI-compatible model instead of `LLM.generate()`.
- Returns exactly `{"id": str, "tool_calls": list[dict], "state_hash": str}`.

- [ ] **Step 1: Update runner tests to inject a fake PydanticAI agent/model factory and fake `ToolEnv`.**

```python
def test_run_sample_returns_only_official_environment_output(monkeypatch, tmp_path, fake_model):
    result = run_sample(sample, "train", tmp_path, catalog, fake_model)
    assert result == {
        "id": "s1",
        "tool_calls": [{"name": "calendar.create", "arguments": {"title": "x"}}],
        "state_hash": "hash-from-env",
    }
```

Keep coverage for no-op, unavailable tool, one write, read-then-write, exactly one `ToolEnv`, and an agent/provider failure that creates no synthetic call.

- [ ] **Step 2: Run runner and integration tests to verify failure.**

Run: `pytest tests/test_runner.py tests/test_integration.py -v`

Expected: FAIL because the current runner calls `LLM.generate()` and parses raw JSON.

- [ ] **Step 3: Refactor `run_sample()` in `src/lifemate/runner.py`.**

Keep sample audio resolution, `allowed_tools()` and exactly one environment creation. Build dependencies/tools/agent from Tasks 1–3, pass a prompt containing only transcript plus permitted context/history, run the agent, then return `env.get_tool_calls()` and `env.get_state_hash()`.

- [ ] **Step 4: Remove `LocalQwenAgent.generate()` from the normal execution path.**

Replace it with a compatibility shim only if needed by external imports; otherwise remove raw JSON parser/prompt modules and their tests in the same change. No code may parse assistant JSON arrays after this task.

- [ ] **Step 5: Run the focused tests to verify success.**

Run: `pytest tests/test_runner.py tests/test_integration.py tests/test_parser.py tests/test_prompting.py -v`

Expected: PASS; remove obsolete test files only if their code is intentionally removed.

- [ ] **Step 6: Commit the runner migration.**

```bash
git add src/lifemate/runner.py src/lifemate/llm.py src/lifemate/agent_schema.py src/lifemate/prompting.py tests
git commit -m "refactor: run tools through pydantic ai"
```

### Task 5: Thêm CLI vLLM, runbook và smoke test offline

**Files:**
- Modify: `src/lifemate/cli.py`
- Modify: `baseline.py`
- Modify: `tests/test_cli.py`
- Create: `RUNBOOK.md`
- Modify: `tests/test_integration.py`

**Interfaces:**
- CLI accepts `--llm-base-url` (default `http://127.0.0.1:8000/v1`) and `--llm-model-name` (default `qwen3-4b`).
- `run_dataset(..., llm_base_url: str, llm_model_name: str, ...) -> None` creates one reusable vLLM model client and one `ToolEnv` per sample.

- [ ] **Step 1: Add failing CLI tests for vLLM defaults, a loopback override and remote URL rejection.**

```python
def test_cli_passes_vllm_options_to_dataset(monkeypatch, tmp_path):
    # invoke main with --llm-base-url http://localhost:9000/v1 --llm-model-name qwen3-4b
    assert captured["llm_base_url"] == "http://localhost:9000/v1"
```

- [ ] **Step 2: Run CLI tests to verify failure.**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL because the options do not exist.

- [ ] **Step 3: Add the vLLM options and reuse one model client in `run_dataset()`.**

Validate the endpoint before iterating samples. Do not perform network/download work in argument parsing.

- [ ] **Step 4: Write `RUNBOOK.md`.**

Include a Linux/Colab command that starts vLLM with local `Qwen/Qwen3-4B` weights, local endpoint and deterministic settings; include a separate baseline command using that endpoint. State clearly that both processes must run in the same offline runtime and that vLLM is not required on Windows local tests.

- [ ] **Step 5: Add an opt-in real smoke command to the runbook and integration test notes.**

It runs one train sample against an already-running local vLLM server, verifies UTF-8 JSONL and the three submission fields, but is skipped by normal CPU-only `pytest`.

- [ ] **Step 6: Run the complete unit suite.**

Run: `$env:PYTHONPATH='src'; pytest -q`

Expected: PASS.

- [ ] **Step 7: Run the real one-sample smoke test when a Linux/Colab GPU and local Qwen checkpoint are available.**

Expected: one valid JSONL result where `tool_calls` and `state_hash` were obtained from `ToolEnv`; no external network call.

- [ ] **Step 8: Commit documentation and CLI integration.**

```bash
git add baseline.py src/lifemate/cli.py tests/test_cli.py tests/test_integration.py RUNBOOK.md
git commit -m "feat: add vllm pydantic agent cli"
```

## Tự kiểm tra kế hoạch

- **Bao phủ spec:** Các ràng buộc endpoint local, PydanticAI, schema tool động, giới hạn read/write, `ToolEnv` và output chính thức lần lượt thuộc Tasks 1–4; CLI/runbook/smoke test thuộc Task 5.
- **Tính nhất quán interface:** `VLLMConfig` từ Task 1 cung cấp model cho Task 2/3; `AgentDependencies` và `run_agent()` từ Tasks 2/3 được runner Task 4 sử dụng; Task 5 chỉ nối cấu hình CLI vào các interface đó.
- **Review focus:** Mỗi mục ở đầu kế hoạch có test sở hữu rõ ràng tại Tasks 1–4.
- **Phạm vi:** Không thay ASR, không thêm Docker/few-shot/fine-tune và không đòi vLLM trên Windows.
