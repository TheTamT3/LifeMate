from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

from .asr import ASR, transcript
from .data import allowed_tools
from .pydantic_agent import AgentDependencies, build_agent, run_agent, tool_name_map


def _tool_env(split: str, sample_id: str, root: Path) -> Any:
    split_dir = root / split
    if str(split_dir) not in sys.path:
        sys.path.insert(0, str(split_dir))
    from zaic_tools import ToolEnv

    return ToolEnv(split, sample_id, root=str(root))


def _sample_with_audio_root(sample: dict[str, Any], root: Path, split: str) -> dict[str, Any]:
    if "audio" not in sample:
        return sample
    copied = dict(sample)
    audio = Path(str(sample["audio"]))
    if not audio.is_absolute():
        candidate = root / split / audio
        if candidate.exists():
            copied["audio"] = str(candidate)
    return copied


def run_sample(
    sample: dict[str, Any],
    split: str,
    root: Path,
    catalog: dict[str, dict[str, Any]],
    llm_model: Any,
    asr: ASR | None = None,
    max_steps: int = 8,
    seed: int = 0,
) -> dict[str, Any]:
    env = _tool_env(split, sample["id"], root)
    tools = allowed_tools(sample, catalog)
    text = transcript(_sample_with_audio_root(sample, root, split), asr)
    tools_by_name = {tool["name"]: tool for tool in tools}
    deps = AgentDependencies(env=env, tools_by_name=tools_by_name, max_steps=max_steps, seed=seed)
    agent = build_agent(llm_model, deps)
    prompt = _build_agent_prompt(sample, text, tools)
    names = tool_name_map(tools)
    history_records = _history_records(sample, names)
    message_history = _to_model_messages(history_records) if history_records else []
    run_agent(
        agent,
        deps,
        prompt,
        message_history=message_history,
        instructions=_build_system_prompt(sample),
    )

    return {
        "id": str(sample["id"]),
        "tool_calls": env.get_tool_calls(),
        "state_hash": env.get_state_hash(),
    }


def _build_system_prompt(sample: dict[str, Any]) -> str:
    """Build dynamic system instructions without exposing labels or app state."""

    context = dict(sample.get("context", {}))
    context.pop("installed_apps", None)
    return "\n".join(
        [
            "You are an offline Vietnamese tool-calling agent.",
            "Use only registered tools and never invent identifiers.",
            "Use a read tool first when a later action needs an unknown ID.",
            "Return no tool call when no action is required.",
            f"Context: {json.dumps(context, ensure_ascii=False)}",
        ]
    )


def _build_agent_prompt(sample: dict[str, Any], text: str, tools: list[dict[str, Any]]) -> str:
    """Build the current request as the user message.

    Tool schemas are registered through PydanticAI and are intentionally not
    duplicated in this message.
    """

    return text


def _history_records(sample: dict[str, Any], names: dict[str, str]) -> list[dict[str, Any]]:
    """Normalize dataset history into role records for PydanticAI."""

    records: list[dict[str, Any]] = []
    for history_index, item in enumerate(sample.get("history", [])):
        role = item.get("role")
        if role == "user":
            records.append(
                {
                    "role": "user",
                    "content": str(item.get("audio_text") or item.get("text") or item.get("content") or ""),
                }
            )
            continue
        if role != "assistant":
            continue

        calls = item.get("tool_calls", [])
        call_records: list[dict[str, Any]] = []
        for call_index, call in enumerate(calls):
            official_name = str(call.get("name", ""))
            call_records.append(
                {
                    "name": names.get(official_name, official_name),
                    "arguments": call.get("arguments", {}),
                    "tool_call_id": f"history_{history_index}_call_{call_index}",
                }
            )
        assistant: dict[str, Any] = {"role": "assistant", "content": str(item.get("text") or "")}
        if call_records:
            assistant["tool_calls"] = call_records
        if assistant["content"] or call_records:
            records.append(assistant)

        for call_index, result in enumerate(item.get("tool_results", [])):
            if call_index >= len(call_records):
                break
            records.append(
                {
                    "role": "tool",
                    "name": call_records[call_index]["name"],
                    "tool_call_id": call_records[call_index]["tool_call_id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return records


def _to_model_messages(records: list[dict[str, Any]]) -> list[Any]:
    """Convert normalized records to PydanticAI message objects."""

    try:
        from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("PydanticAI message support is required for non-empty history") from exc

    messages: list[Any] = []
    for record in records:
        if record["role"] == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(record["content"])]))
        elif record["role"] == "assistant":
            parts: list[Any] = []
            if record.get("content"):
                parts.append(TextPart(record["content"]))
            parts.extend(
                ToolCallPart(
                    tool_name=call["name"],
                    args=call["arguments"],
                    tool_call_id=call["tool_call_id"],
                )
                for call in record.get("tool_calls", [])
            )
            messages.append(ModelResponse(parts=parts))
        elif record["role"] == "tool":
            messages.append(
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name=record["name"],
                            content=json.loads(record["content"]),
                            tool_call_id=record["tool_call_id"],
                        )
                    ]
                )
            )
    return messages
