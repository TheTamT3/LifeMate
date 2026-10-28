"""PydanticAI tool construction for the catalog-driven LifeMate agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, create_model


@dataclass
class AgentDependencies:
    env: Any
    tools_by_name: dict[str, dict[str, Any]]
    max_steps: int
    calls: list[dict[str, Any]] = field(default_factory=list)
    round_calls: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class _FallbackUsageLimits:
    request_limit: int


def _safe_name(name: str, index: int) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "tool"
    return f"lifemate_tool_{index}_{value}"


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
        f"{_safe_name(str(tool.get('name', 'tool')), 0)}Arguments",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def validate_catalog_arguments(tool: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    model = catalog_argument_model(tool)
    value = model.model_validate(arguments)
    groups = (tool.get("parameters") or {}).get("x-one-of", [])
    if groups and not any(all(name in arguments and arguments[name] is not None for name in option) for option in groups):
        raise ValueError(f"arguments do not satisfy x-one-of for {tool.get('name')}")
    return value.model_dump(exclude_none=True)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return str(value)


def build_tool_definitions(deps: AgentDependencies) -> list[Any]:
    try:
        from pydantic_ai import Tool
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("PydanticAI is required to build agent tools") from exc

    definitions: list[Any] = []
    for index, (official_name, tool) in enumerate(deps.tools_by_name.items()):
        argument_model = catalog_argument_model(tool)
        internal_name = _safe_name(official_name, index)

        def validate(_ctx: Any, arguments: dict[str, Any], *, _tool=tool) -> None:
            validate_catalog_arguments(_tool, arguments)

        def invoke(ctx: Any, *, _official=official_name, _tool=tool, **arguments: Any) -> Any:
            parsed = validate_catalog_arguments(_tool, arguments)
            result = ctx.deps.env.call(_official, parsed) if ctx is not None and hasattr(ctx, "deps") else deps.env.call(_official, parsed)
            deps.calls.append({"name": _official, "arguments": parsed, "kind": _tool.get("kind", "write")})
            return _json_safe(result)

        schema = argument_model.model_json_schema()
        definitions.append(
            Tool.from_schema(
                invoke,
                name=internal_name,
                description=str(tool.get("description", "")),
                json_schema=schema,
                takes_ctx=True,
                args_validator=validate,
                sequential=True,
            )
        )
    return definitions


def build_agent(model: Any, deps: AgentDependencies) -> Any:
    try:
        from pydantic_ai import Agent
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("PydanticAI is required to build the agent") from exc

    return Agent(
        model=model,
        deps_type=AgentDependencies,
        tools=build_tool_definitions(deps),
        system_prompt=(
            "You are an offline Vietnamese tool-calling agent. Use only registered tools, "
            "never invent identifiers, and return no action when no tool is needed. "
            "Use a read tool first when a later action needs an unknown ID."
        ),
    )


def run_agent(agent: Any, deps: AgentDependencies, prompt: str) -> Any:
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
    try:
        return agent.run_sync(
            prompt,
            deps=deps,
            usage_limits=usage_limits,
            model_settings={"temperature": 0, "top_p": 1},
        )
    except Exception as exc:  # provider failures must not create synthetic calls
        deps.error = str(exc)
        return None
