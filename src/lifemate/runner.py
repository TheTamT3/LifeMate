from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

from .asr import ASR, transcript
from .data import allowed_tools
from .pydantic_agent import AgentDependencies, build_agent, run_agent


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
    run_agent(agent, deps, prompt)

    return {
        "id": str(sample["id"]),
        "tool_calls": env.get_tool_calls(),
        "state_hash": env.get_state_hash(),
    }


def _build_agent_prompt(sample: dict[str, Any], text: str, tools: list[dict[str, Any]]) -> str:
    """Build the user message without exposing labels or environment state."""

    context = dict(sample.get("context", {}))
    context.pop("installed_apps", None)
    payload = {
        "request": text,
        "context": context,
        "history": sample.get("history", []),
        "available_tools": [
            {
                "name": tool["name"],
                "kind": tool.get("kind"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            }
            for tool in tools
        ],
        "rules": [
            "Use only the registered tools.",
            "Do not invent identifiers; use a read tool first when needed.",
            "Return no tool call when no action is required.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
