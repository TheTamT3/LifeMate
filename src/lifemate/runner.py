from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

from .agent_schema import ToolCall, parse_calls
from .asr import ASR, transcript
from .data import allowed_tools
from .prompting import build_prompt


class LLM(Protocol):
    def generate(self, prompt: str) -> str: ...


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
    llm: LLM,
    asr: ASR | None = None,
    max_steps: int = 8,
) -> dict[str, Any]:
    env = _tool_env(split, sample["id"], root)
    tools = allowed_tools(sample, catalog)
    text = transcript(_sample_with_audio_root(sample, root, split), asr)
    allowed_names = {tool["name"] for tool in tools}
    observations: list[dict[str, Any]] = []

    for _ in range(max_steps):
        calls: list[ToolCall] = parse_calls(
            llm.generate(build_prompt(sample, text, tools, observations)), allowed_names
        )
        if not calls:
            break
        progressed = False
        for call in calls:
            result = env.call(call.name, call.arguments)
            observations.append({"call": call.model_dump(), "result": result})
            progressed = True
        if not progressed:
            break
        if not all(catalog.get(call.name, {}).get("kind") == "read" for call in calls):
            break

    return {
        "id": str(sample["id"]),
        "tool_calls": env.get_tool_calls(),
        "state_hash": env.get_state_hash(),
    }
