"""PydanticAI tool construction for the catalog-driven LifeMate agent."""

from __future__ import annotations

import json
import inspect
import re
import asyncio
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, create_model


_batch_runner = ContextVar('lifemate_batch_runner', default=None)

VIETNAMESE_REASONING = (
    "Sử dụng tiếng Việt cho phần suy luận và giải thích được trả về. "
    "Giữ nguyên tên công cụ, khóa JSON, mã định danh và các giá trị kỹ thuật. "
    "Khi gọi công cụ, tuân thủ đúng schema; không dịch tên công cụ hoặc tên tham số."
)


def qwen_thinking_settings(seed=0):
    return {'temperature': 0.6, 'top_p': 0.95, 'seed': seed,
            'extra_body': {'top_k': 20, 'min_p': 0,
                           'chat_template_kwargs': {'enable_thinking': True}}}


def without_thinking(messages):
    """Keep original responses for tracing, but omit reasoning in model history."""
    return [replace(message, parts=[part for part in message.parts
                                   if getattr(part, 'part_kind', None) != 'thinking'])
            if getattr(message, 'kind', None) == 'response' else message
            for message in messages]


@contextmanager
def agent_event_loop():
    """Keep pooled async model connections on one loop for a batch."""
    if _batch_runner.get() is not None:
        yield _batch_runner.get()
        return
    with asyncio.Runner() as runner:
        token = _batch_runner.set(runner)
        try:
            yield runner
        finally:
            _batch_runner.reset(token)


def run_agent_coroutine(coroutine):
    runner = _batch_runner.get()
    return runner.run(coroutine, context=copy_context()) if runner is not None else asyncio.run(coroutine)


@dataclass
class AgentDependencies:
    env: Any
    tools_by_name: dict[str, dict[str, Any]]
    max_steps: int
    seed: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)
    round_calls: list[list[str]] = field(default_factory=list)
    argument_normalizations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _FallbackUsageLimits:
    request_limit: int


def _safe_name(name: str) -> str:
    """Convert a catalog name to the provider-safe wire name.

    OpenAI-compatible tool names cannot contain dots, so keep the app prefix
    and replace separators: ``weather.get_forecast`` becomes
    ``weather_get_forecast``.
    """

    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "tool"


def tool_name_map(tools: list[dict[str, Any]]) -> dict[str, str]:
    """Map catalog names to stable PydanticAI wire names."""

    mapping = {
        str(tool["name"]): _safe_name(str(tool["name"]))
        for tool in tools
    }
    if len(mapping.values()) != len(set(mapping.values())):
        raise ValueError("catalog tool names collide after provider-safe normalization")
    return mapping


def _annotation(spec: dict[str, Any]) -> Any:
    kind = spec.get("type")
    if "enum" in spec:
        return Literal[tuple(spec["enum"])]
    if kind == "string":
        return StrictStr
    if kind == "integer":
        return StrictInt
    if kind == "number":
        return StrictFloat
    if kind == "boolean":
        return StrictBool
    if kind == "array":
        item = spec.get("items", {"type": "string"})
        return list[_annotation(item)]
    if kind == "object":
        properties = spec.get("properties", {})
        required = set(spec.get("required", []))
        fields: dict[str, tuple[Any, Any]] = {}
        for name, child in properties.items():
            default = ... if name in required else None
            fields[name] = (_annotation(child), Field(default=default, description=child.get("description")))
        return create_model("CatalogNestedObject", __config__=ConfigDict(extra="forbid"), **fields)
    raise ValueError(f"unsupported catalog parameter type: {kind!r}")


def catalog_argument_model(tool: dict[str, Any]) -> type[BaseModel]:
    parameters = tool.get("parameters") or {"type": "object", "properties": {}, "required": []}
    if parameters.get("type") != "object":
        raise ValueError(f"tool {tool.get('name')!r} must have an object parameter schema")
    properties = parameters.get("properties", {})
    required = set(parameters.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for name, spec in properties.items():
        description = spec.get("description")
        default = ... if name in required else None
        constraints: dict[str, Any] = {"default": default, "description": description}
        if "minimum" in spec:
            constraints["ge"] = spec["minimum"]
        if "exclusiveMinimum" in spec:
            constraints["gt"] = spec["exclusiveMinimum"]
        fields[name] = (_annotation(spec), Field(**constraints))
    return create_model(
        f"{_safe_name(str(tool.get('name', 'tool')))}Arguments",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def validate_catalog_arguments(tool: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    model = catalog_argument_model(tool)
    value = model.model_validate(arguments)
    groups = (tool.get("parameters") or {}).get("x-one-of", [])
    if groups and not any(all(name in arguments and arguments[name] is not None for name in option) for option in groups):
        raise ValueError(f"arguments do not satisfy x-one-of for {tool.get('name')}")
    parsed = value.model_dump(exclude_none=True)
    _validate_formats(parsed, (tool.get("parameters") or {}).get("properties", {}))
    return parsed


def _validate_formats(value: Any, spec: dict[str, Any]) -> None:
    """Apply the small, catalog-supported JSON Schema format subset."""
    if not isinstance(spec, dict):
        return
    if isinstance(value, dict):
        properties = spec.get("properties", spec)
        for name, child in properties.items():
            if name in value:
                _validate_formats(value[name], child)
        return
    if isinstance(value, list):
        item_spec = spec.get("items", {})
        for item in value:
            _validate_formats(item, item_spec)
        return
    fmt = spec.get("format")
    if not fmt or value is None:
        return
    try:
        if fmt == "date":
            date.fromisoformat(value)
        elif fmt == "date-time":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif fmt == "time":
            time.fromisoformat(value.replace("Z", "+00:00"))
        elif fmt == "email":
            if not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", value):
                raise ValueError
        elif fmt == "uuid":
            import uuid

            uuid.UUID(value)
        else:
            raise ValueError(f"unsupported catalog format: {fmt!r}")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {fmt} value: {value!r}") from exc


def _json_safe(value: Any) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded) > 16_384:
            encoded = encoded[:16_384]
        return json.loads(encoded)
    except (TypeError, ValueError):
        return str(value)


def _catalog_json_schema(model: type[BaseModel], tool: dict[str, Any]) -> dict[str, Any]:
    schema = model.model_json_schema()
    parameters = tool.get("parameters") or {}
    for extension in ("x-one-of", "x-ref", "x-match"):
        if extension in parameters:
            schema[extension] = parameters[extension]
    for name, spec in parameters.get("properties", {}).items():
        if name not in schema.get("properties", {}):
            continue
        for extension in ("x-ref", "x-match", "format"):
            if extension in spec:
                schema["properties"][name][extension] = spec[extension]
    return schema


def build_tool_definitions(deps: AgentDependencies) -> list[Any]:
    try:
        from pydantic_ai import Tool
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("PydanticAI is required to build agent tools") from exc

    definitions: list[Any] = []
    wire_names: set[str] = set()
    for official_name, tool in deps.tools_by_name.items():
        argument_model = catalog_argument_model(tool)
        internal_name = _safe_name(official_name)
        if internal_name in wire_names:
            raise ValueError(f"catalog tool name collision after normalization: {internal_name}")
        wire_names.add(internal_name)

        def invoke(ctx: Any, *, _official=official_name, _tool=tool, **arguments: Any) -> Any:
            parsed = validate_catalog_arguments(_tool, arguments)
            result = ctx.deps.env.call(_official, parsed) if ctx is not None and hasattr(ctx, "deps") else deps.env.call(_official, parsed)
            deps.calls.append({"name": _official, "arguments": parsed, "kind": _tool.get("kind", "write")})
            return _json_safe(result)

        schema = _catalog_json_schema(argument_model, tool)
        description = str(tool.get("description", ""))
        if official_name not in description:
            description = f"Tên công cụ chính thức: {official_name}. {description}".strip()
        if not schema.get("properties"):
            description += (
                " Công cụ này không nhận tham số. Luôn gọi với arguments {}."
                " Không truyền bất kỳ trường nào."
            )
        definitions.append(
            Tool.from_schema(
                invoke,
                name=internal_name,
                description=description,
                json_schema=schema,
                takes_ctx=True,
                sequential=True,
            )
        )
    return definitions


def _normalizing_model(model: Any, deps: AgentDependencies) -> Any:
    """Repair object payloads only for closed, parameterless catalog tools.

    Wrap outside provider tracing so the original response remains observable.
    Copy responses/parts rather than altering the provider's response in place.
    LifeMate uses non-streaming requests through Agent.iter.
    """
    from pydantic_ai.models.wrapper import WrapperModel

    eligible = {}
    for name, tool in deps.tools_by_name.items():
        schema = _catalog_json_schema(catalog_argument_model(tool), tool)
        if (schema.get("type") == "object" and schema.get("properties") == {}
                and schema.get("additionalProperties") is False
                and not schema.get("required") and not schema.get("x-one-of")):
            eligible[_safe_name(name)] = name

    class NormalizingModel(WrapperModel):
        async def request(self, *args: Any, **kwargs: Any) -> Any:
            response = await self.wrapped.request(*args, **kwargs)
            parts = []
            for part in response.parts:
                if (getattr(part, "part_kind", None) == "tool-call"
                        and part.tool_name in eligible):
                    original = part.args
                    try:
                        parsed = json.loads(original) if isinstance(original, str) else original
                    except (ValueError, TypeError):
                        parsed = None
                    if isinstance(parsed, dict) and parsed:
                        deps.argument_normalizations.append({
                            "tool": eligible[part.tool_name],
                            "tool_call_id": part.tool_call_id,
                            "original_arguments": deepcopy(original),
                            "normalized_arguments": {},
                            "normalization_applied": True,
                        })
                        part = replace(part, args={})
                parts.append(part)
            return replace(response, parts=parts)

    return NormalizingModel(model)


def build_agent(model: Any, deps: AgentDependencies) -> Any:
    try:
        from pydantic_ai import Agent
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("PydanticAI is required to build the agent") from exc

    return Agent(
        model=_normalizing_model(model, deps),
        deps_type=AgentDependencies,
        tools=build_tool_definitions(deps),
        history_processors=[without_thinking],
        # Instructions are merged with per-sample instructions into one leading
        # system message, including when a conversation history is supplied.
        instructions=(
            "Bạn là trợ lý tiếng Việt hoạt động ngoại tuyến và thực hiện yêu cầu bằng cách gọi công cụ. "
            "Chỉ sử dụng các công cụ đã đăng ký, không tự bịa mã định danh và không thực hiện thao tác khi không cần gọi công cụ. "
            "Nếu thao tác tiếp theo cần một mã định danh chưa biết, hãy gọi công cụ đọc dữ liệu để tra cứu trước."
            + " " + VIETNAMESE_REASONING
        ),
    )


def run_agent(
    agent: Any,
    deps: AgentDependencies,
    prompt: str,
    *,
    message_history: list[Any] | None = None,
    instructions: str | None = None,
) -> Any:
    """Run one PydanticAI conversation with deterministic settings.

    PydanticAI owns the model/tool message loop. The registered tools are
    sequential barriers, and the prompt instructs the model to finish after a
    write/meta operation; the request limit is the final safety bound.
    """

    try:
        from pydantic_ai import UsageLimits

        usage_limits = UsageLimits(request_limit=deps.max_steps)
    except ImportError:  # unit tests can run without optional PydanticAI deps
        usage_limits = _FallbackUsageLimits(request_limit=deps.max_steps)
    settings = qwen_thinking_settings(deps.seed)
    try:
        if hasattr(agent, "iter"):
            import asyncio

            async def drive() -> Any:
                async with agent.iter(
                    prompt,
                    deps=deps,
                    message_history=message_history or [],
                    instructions=instructions,
                    usage_limits=usage_limits,
                    model_settings=settings,
                ) as agent_run:
                    node = agent_run.next_node
                    while node.__class__.__name__ != "End":
                        before = len(deps.calls)
                        node = await agent_run.next(node)
                        new_calls = deps.calls[before:]
                        if any(call["kind"] != "read" for call in new_calls):
                            break
                    return getattr(agent_run, "result", None)

            return run_agent_coroutine(drive())
        run_kwargs = {
            "deps": deps,
            "message_history": message_history or [],
            "usage_limits": usage_limits,
            "model_settings": settings,
        }
        if instructions is not None and "instructions" in inspect.signature(agent.run_sync).parameters:
            run_kwargs["instructions"] = instructions
        return agent.run_sync(prompt, **run_kwargs)
    except Exception as exc:  # provider failures must not create synthetic calls
        deps.error = str(exc)
        return None
