"""Train-only gold tool availability without reading app state.

Only label call *names* are consumed. Never replay gold calls or use their
arguments, results or final state to construct model inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .data import allowed_tools

ORACLE_VERSION = 'gold-tools-only-v3'
ORACLE_INSTRUCTIONS = (
    'Danh sách công cụ đã được chọn phù hợp với yêu cầu. '
    'Tự quyết định công cụ cần gọi, thứ tự, số lần gọi và arguments theo yêu cầu '
    'còn hiệu lực, context, hội thoại và kết quả công cụ. '
    'Không bắt buộc gọi tất cả công cụ. Không tự tạo ID hoặc dữ kiện còn thiếu. '
    'Lấy dữ liệu cần thiết qua công cụ; dùng kết quả thực thi để xác nhận '
    'thay đổi và chỉ báo hoàn tất khi thao tác thành công.'
)


@dataclass(frozen=True)
class OracleInputs:
    tool_names: tuple[str, ...]


def prepare_oracle_inputs(sample: dict[str, Any], catalog: dict[str, dict[str, Any]],
                          root: Path, split: str) -> OracleInputs:
    if split != 'train':
        raise ValueError('oracle-tools-source requires train labels')
    label = sample.get('label')
    calls = label.get('tool_calls') if isinstance(label, dict) else None
    if not isinstance(calls, list):
        raise ValueError(f"Sample {sample.get('id')} requires label.tool_calls")
    names = set()
    available = {tool['name'] for tool in allowed_tools(sample, catalog)}
    for call in calls:
        name = call.get('name') if isinstance(call, dict) else None
        if not isinstance(name, str) or name not in catalog:
            raise ValueError(f"Sample {sample.get('id')}: unknown label tool {name!r}")
        if name not in available:
            raise ValueError(f"Sample {sample.get('id')}: tool {name!r} is not available")
        names.add(name)
    return OracleInputs(tuple(sorted(names)))
