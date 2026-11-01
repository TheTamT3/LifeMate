from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dotted_order(run_id: str, start_time: datetime | None = None) -> str:
    return f"{(start_time or _now()).strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"


def _safe_output(value: Any) -> Any:
    if callable(getattr(value, 'all_messages', None)):
        return {'output': _safe_output(getattr(value, 'output', None)),
                'messages': _safe_output(value.all_messages())}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _safe_output(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): _safe_output(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_output(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
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
        self._parent = ContextVar(f'langsmith_parent_{root_run_id}', default=(root_run_id, root_dotted_order))
        self._last_start: datetime | None = None
        self._runs: dict[str, tuple[datetime, str, str]] = {}

    def start(self, name: str, run_type: str, inputs: dict[str, Any], metadata: dict[str, Any] | None = None) -> tuple[str, str]:
        run_id = str(uuid4())
        parent_id, parent_order = self._parent.get()
        start_time = _now()
        if self._last_start is not None and start_time <= self._last_start:
            start_time = self._last_start + timedelta(microseconds=1)
        self._last_start = start_time
        dotted_order = f"{parent_order}.{_dotted_order(run_id, start_time)}"
        self._runs[run_id] = (start_time, dotted_order, parent_id)
        self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=_safe_output(inputs),
            project_name=self.project,
            id=run_id,
            run_id=run_id,
            parent_run_id=parent_id,
            trace_id=self.root_run_id,
            dotted_order=dotted_order,
            start_time=start_time,
            extra={"metadata": metadata or {}},
        )
        return run_id, dotted_order

    def finish(self, run_id: str, *, outputs: Any = None, error: Exception | None = None) -> None:
        start_time, order, parent_id = self._runs[run_id]
        payload: dict[str, Any] = {
            'end_time': max(_now(), self._last_start or start_time, start_time),
            'trace_id': self.root_run_id, 'dotted_order': order,
            'parent_run_id': parent_id,
        }
        if error is not None:
            payload["error"] = f"{type(error).__name__}: {error}"
        else:
            safe_outputs = _safe_output(outputs)
            payload["outputs"] = (
                safe_outputs if isinstance(safe_outputs, dict) else {"output": safe_outputs}
            )
        self.client.update_run(run_id, **payload)

    def trace(self, name: str, run_type: str, inputs: dict[str, Any], fn: Callable[[], Any], metadata: dict[str, Any] | None = None) -> Any:
        run_id, order = self.start(name, run_type, inputs, metadata)
        token = self._parent.set((run_id, order))
        try:
            result = fn()
        except Exception as exc:
            self.finish(run_id, error=exc)
            raise
        finally:
            self._parent.reset(token)
        self.finish(run_id, outputs=result)
        return result

    async def trace_model(self, model_name, inputs, fn):
        run_id, order = self.start('llm.' + model_name, 'llm', inputs,
            {'ls_provider': 'openai', 'ls_model_name': model_name})
        token = self._parent.set((run_id, order))
        try:
            response = await fn()
            usage = _safe_output(getattr(response, 'usage', {}))
            usage = usage if isinstance(usage, dict) else {}
            input_tokens = usage.get('input_tokens') or 0
            output_tokens = usage.get('output_tokens') or 0
            self.finish(run_id, outputs={
                'response': _safe_output(response),
                'usage_metadata': {'input_tokens': input_tokens, 'output_tokens': output_tokens,
                                   'total_tokens': input_tokens + output_tokens},
            })
            return response
        except Exception as exc:
            self.finish(run_id, error=exc)
            raise
        finally:
            self._parent.reset(token)


def tracing_model(model, tracer):
    """Trace non-streaming requests used by LifeMate's Agent.iter loop."""
    from pydantic_ai.models.wrapper import WrapperModel

    class TracedModel(WrapperModel):
        async def request(self, messages, model_settings, model_request_parameters):
            return await tracer.trace_model(self.model_name, {
                'messages': _safe_output(messages),
                'model_settings': _safe_output(model_settings),
                'request_parameters': _safe_output(model_request_parameters),
            }, lambda: self.wrapped.request(messages, model_settings, model_request_parameters))

    return TracedModel(model)


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
