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
        "task": "Hiểu yêu cầu tiếng Việt và chỉ gọi các công cụ đã cài đặt cần thiết để thực hiện yêu cầu.",
        "request": transcript,
        "context": sample.get("context", {}),
        "history": sample.get("history", []),
        "available_tools": compact_tools,
        "previous_tool_results": observations,
        "output_format": [{"name": "app.tool", "arguments": {}}],
        "rules": [
            "Chỉ trả về một mảng JSON hợp lệ.",
            "Dùng chính xác tên công cụ và các tham số hợp lệ.",
            "Trả về [] khi không cần gọi công cụ nào.",
            "Không tự bịa mã định danh; nếu chưa biết mã, hãy gọi công cụ đọc dữ liệu để tra cứu trước.",
            "Không cung cấp hoặc yêu cầu ví dụ mẫu trong lời nhắc.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
