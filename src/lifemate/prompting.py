from __future__ import annotations

import json
from typing import Any


def build_prompt(
    sample: dict[str, Any],
    transcript: str,
    tools: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> str:
    compact_tools = [
        {
            "name": tool["name"],
            "kind": tool.get("kind"),
            "description": tool.get("description", ""),
            "parameters": tool.get("parameters", {}),
        }
        for tool in tools
    ]
    payload = {
        "task": "Interpret the Vietnamese request and call only necessary installed tools.",
        "request": transcript,
        "context": sample.get("context", {}),
        "history": sample.get("history", []),
        "available_tools": compact_tools,
        "previous_tool_results": observations,
        "output_format": [{"name": "app.tool", "arguments": {}}],
        "rules": [
            "Return only a JSON array.",
            "Use exact tool names and valid arguments.",
            "Return [] when no tool is needed.",
            "Do not invent IDs; query a read tool first when an ID is unknown.",
            "No Few-shot examples are provided or expected.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
