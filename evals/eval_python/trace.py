"""Normalize agent tool events before passing them to DeepEval metrics."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any


class ToolTraceError(ValueError):
    """Raised when an agent trace cannot provide authoritative tool evidence."""


def normalize_tool_trace(agent_trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return canonical tool-call evidence from a complete agent trace.

    A backend must explicitly mark the trace as complete. This prevents a
    missing SDK extraction feature from being treated as a valid empty trace.
    """
    if agent_trace.get("trace_status") != "complete":
        status = agent_trace.get("trace_status", "missing")
        raise ToolTraceError(f"Tool trace is not complete: {status}")

    raw_calls = agent_trace.get("tool_calls")
    if not isinstance(raw_calls, list):
        raise ToolTraceError("Complete tool trace must contain a list of tool_calls")

    return [_normalize_tool_call(raw_call, index) for index, raw_call in enumerate(raw_calls)]


def to_deepeval_tool_calls(
    normalized_calls: list[dict[str, Any]],
    tool_call_factory: Callable[..., Any] | None = None,
) -> list[Any]:
    """Create DeepEval ``ToolCall`` values from canonical tool evidence."""
    if tool_call_factory is None:
        try:
            from deepeval.test_case import ToolCall
        except ImportError as error:
            raise RuntimeError("Install the deepeval extra to create ToolCall values") from error
        tool_call_factory = ToolCall

    return [
        tool_call_factory(name=call["name"], arguments=call["arguments"])
        for call in normalized_calls
    ]


def _normalize_tool_call(raw_call: Any, index: int) -> dict[str, Any]:
    name = _read_field(raw_call, "name", "tool_name")
    if not isinstance(name, str) or not name:
        raise ToolTraceError(f"Tool call {index} has no tool name")

    arguments = _read_field(raw_call, "arguments", "args", "input")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise ToolTraceError(f"Tool call {index} has invalid JSON arguments") from error
    if not isinstance(arguments, Mapping):
        raise ToolTraceError(f"Tool call {index} arguments must be an object")

    result = _read_field(raw_call, "result", "output", default=None)
    error_category = _read_field(raw_call, "error_category", "error", default=None)
    event_id = _read_field(raw_call, "event_id", "id", default=None)
    return {
        "name": name,
        "arguments": dict(arguments),
        "result": result,
        "error_category": error_category,
        "event_id": event_id,
        "index": index,
    }


def _read_field(raw_call: Any, *names: str, default: Any = ... ) -> Any:
    for name in names:
        if isinstance(raw_call, Mapping) and name in raw_call:
            return raw_call[name]
        if hasattr(raw_call, name):
            return getattr(raw_call, name)
    return default
