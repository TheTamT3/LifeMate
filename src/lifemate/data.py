from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for app in payload.get("apps", []):
        for tool in app.get("tools", []):
            if isinstance(tool, dict) and isinstance(tool.get("name"), str):
                result[tool["name"]] = tool
    return result


def allowed_tools(sample: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    installed = sample.get("context", {}).get("installed_apps", {}) or {}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for app in installed.values():
        for name in app.get("tools", []):
            if name not in seen and name in catalog:
                result.append(catalog[name])
                seen.add(name)
    # The official runtime exposes this catalogued system tool for requesting
    # missing information even when no application advertises it.
    if "sys.ask_missing_info" in catalog and "sys.ask_missing_info" not in seen:
        result.append(catalog["sys.ask_missing_info"])
    return result


def split_paths(root: Path, split: Literal["train", "public_test", "private_test"]) -> tuple[Path, Path]:
    split_dir = root / split
    return split_dir / f"{split}.jsonl", split_dir / f"{split}_tools_catalog.json"
