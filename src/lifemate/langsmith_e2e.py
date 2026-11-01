from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dotted_order(run_id: str) -> str:
    return f"{_now().strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"


def _safe_output(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return {"repr": repr(value)}


class LangSmithE2ETracer:
    """Small opt-in tracer used only by the real E2E smoke CLI."""

    def __init__(self, client: Any, project: str, root_run_id: str, root_dotted_order: str) -> None:
        self.client = client
        self.project = project
        self.root_run_id = root_run_id
        self.root_dotted_order = root_dotted_order

    def start(self, name: str, run_type: str, inputs: dict[str, Any], metadata: dict[str, Any] | None = None) -> tuple[str, str]:
        run_id = str(uuid4())
        dotted_order = f"{self.root_dotted_order}.{_dotted_order(run_id)}"
        self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=_safe_output(inputs),
            project_name=self.project,
            id=run_id,
            run_id=run_id,
            parent_run_id=self.root_run_id,
            trace_id=self.root_run_id,
            dotted_order=dotted_order,
            extra={"metadata": metadata or {}},
        )
        return run_id, dotted_order

    def finish(self, run_id: str, *, outputs: Any = None, error: Exception | None = None) -> None:
        payload: dict[str, Any] = {"end_time": _now()}
        if error is not None:
            payload["error"] = f"{type(error).__name__}: {error}"
        else:
            safe_outputs = _safe_output(outputs)
            payload["outputs"] = (
                safe_outputs if isinstance(safe_outputs, dict) else {"output": safe_outputs}
            )
        self.client.update_run(run_id, **payload)

    def trace(self, name: str, run_type: str, inputs: dict[str, Any], fn: Callable[[], Any], metadata: dict[str, Any] | None = None) -> Any:
        run_id, _ = self.start(name, run_type, inputs, metadata)
        try:
            result = fn()
        except Exception as exc:
            self.finish(run_id, error=exc)
            raise
        self.finish(run_id, outputs=result)
        return result


class TracingToolEnv:
    """Delegate ToolEnv operations while tracing each real tool execution."""

    def __init__(self, env: Any, tracer: LangSmithE2ETracer) -> None:
        self._env = env
        self._tracer = tracer

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._tracer.trace(
            f"tool.{name}",
            "tool",
            {"name": name, "arguments": arguments},
            lambda: self._env.call(name, arguments),
        )

    def get_tool_calls(self) -> Any:
        return self._env.get_tool_calls()

    def get_state_hash(self) -> str:
        return self._env.get_state_hash()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)
