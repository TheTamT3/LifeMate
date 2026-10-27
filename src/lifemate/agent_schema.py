from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    arguments: dict[str, Any]


def parse_calls(raw: str, allowed_names: set[str]) -> list[ToolCall]:
    match = re.search(r"\[[\s\S]*\]", raw.strip())
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    calls: list[ToolCall] = []
    for item in value:
        try:
            call = ToolCall.model_validate(item)
        except ValidationError:
            continue
        if call.name in allowed_names:
            calls.append(call)
    return calls
