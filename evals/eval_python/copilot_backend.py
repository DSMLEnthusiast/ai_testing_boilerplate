"""Copilot SDK LLM backend for agent evaluation."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


def _approve_permission_request(_request: Any, _context: dict[str, str]) -> dict[str, Any]:
    return {"kind": "approved", "rules": []}


def _canonical_tool_name(name: Any) -> Any:
    if isinstance(name, str) and name.startswith("math-mcp-"):
        return name.removeprefix("math-mcp-")
    return name


class BaseLLM(ABC):
    """Abstract base class for LLM evaluation backends.

    Implementations must handle running prompts and returning normalized results
    with 'response', 'tool_calls', 'tool_results', 'usage', and 'latency_ms'.
    """

    @abstractmethod
    def run(self, prompt: str) -> dict[str, Any]:
        """Run a prompt synchronously.

        Args:
            prompt: The prompt to evaluate

        Returns:
            Dict with keys:
                - response: str, the model's response
                - tool_calls: list, any tool calls made
                - tool_results: list, results from tool calls
                - usage: dict, token usage (input_tokens, output_tokens)
                - latency_ms: float, execution time in milliseconds
        """
        pass


class CopilotLLM(BaseLLM):
    """Run a prompt through Copilot SDK with the shared MCP server attached."""

    def __init__(self, **session_options: Any) -> None:
        self.session_options = session_options

    def run(self, prompt: str) -> dict[str, Any]:
        """Synchronous wrapper for async evaluation."""
        return asyncio.run(self.run_async(prompt))

    async def run_async(self, prompt: str) -> dict[str, Any]:
        """Run a prompt through Copilot with MCP tools attached.

        Returns:
            Dict with 'response', 'tool_calls', 'tool_results', 'usage', 'latency_ms'.
        """
        try:
            from copilot import CopilotClient
        except ImportError as error:
            raise RuntimeError("Install github-copilot-sdk to run Copilot-backed evaluations") from error

        started = time.perf_counter()
        root = Path(__file__).resolve().parents[2]
        client = CopilotClient()
        client_started = False
        tool_calls = []
        tool_calls_by_id: dict[str, dict[str, Any]] = {}
        tool_results = []
        response_text = ""
        usage = {}
        trace_status = "unavailable"
        provider_error = None
        failure_category = None

        try:
            await client.start()
            client_started = True
            session = await client.create_session({
                "model": self.session_options.get("model", os.environ.get("COPILOT_MODEL", "gpt-5")),
                "on_permission_request": _approve_permission_request,
                "mcp_servers": {
                    "math-mcp": {
                        "type": "stdio",
                        "tools": ["*"],
                        "command": sys.executable,
                        "args": ["-m", "mcp_app.server"],
                        "cwd": str(root),
                        "env": {"PYTHONPATH": str(root / "src")},
                    }
                },
            })

            def handle_event(event: Any) -> None:
                event_type = getattr(getattr(event, "type", None), "value", None)
                data = getattr(event, "data", None)
                if event_type == "assistant.message":
                    for request in getattr(data, "tool_requests", None) or []:
                        tool_call_id = getattr(request, "tool_call_id", None)
                        if not isinstance(tool_call_id, str):
                            continue
                        tool_calls_by_id[tool_call_id] = {
                            "name": _canonical_tool_name(getattr(request, "name", None)),
                            "arguments": getattr(request, "arguments", {}),
                            "event_id": tool_call_id,
                        }
                elif event_type == "tool.execution_complete":
                    tool_call_id = getattr(data, "tool_call_id", None)
                    if not isinstance(tool_call_id, str):
                        return
                    tool_call = tool_calls_by_id.get(tool_call_id)
                    if tool_call is None:
                        return
                    result = getattr(data, "result", None)
                    tool_call["result"] = getattr(result, "content", result)

            unsubscribe = session.on(handle_event)
            response = await session.send_and_wait({"prompt": prompt})
            unsubscribe()

            # Extract response content
            if hasattr(response.data, "content"):
                response_text = response.data.content
            elif hasattr(response.data, "text"):
                response_text = response.data.text
            else:
                response_text = str(response.data)

            tool_calls = list(tool_calls_by_id.values())
            tool_results = [call.get("result") for call in tool_calls if "result" in call]
            trace_status = "complete"

            # Extract usage if available
            if hasattr(response, "usage"):
                usage = {
                    "input_tokens": getattr(response.usage, "input_tokens", 0),
                    "output_tokens": getattr(response.usage, "output_tokens", 0),
                }
        except Exception as error:
            provider_error = str(error)
            failure_category = "provider_error"
            trace_status = "provider_error"

        finally:
            if client_started:
                await client.stop()

        latency_ms = (time.perf_counter() - started) * 1000

        return {
            "response": response_text,
            "scenario_id": self.session_options.get("scenario_id"),
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "trace_status": trace_status,
            "provider_error": provider_error,
            "failure_category": failure_category,
            "usage": usage,
            "latency_ms": latency_ms,
        }


async def run_batch_async(
    scenarios: list[dict[str, Any]],
    backend: BaseLLM,
    *,
    concurrency: int = 1,
) -> list[dict[str, Any]]:
    """Run multiple scenarios concurrently.

    Args:
        scenarios: List of scenario dicts with 'prompt' field
        backend: CopilotLLM instance
        concurrency: Number of concurrent requests

    Returns:
        List of results in scenario order
    """
    import asyncio

    semaphore = asyncio.Semaphore(concurrency)

    async def run_with_semaphore(scenario: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await backend.run_async(scenario["prompt"])

    tasks = [run_with_semaphore(s) for s in scenarios]
    return await asyncio.gather(*tasks, return_exceptions=True)


def run_batch(
    scenarios: list[dict[str, Any]],
    backend: BaseLLM,
    *,
    concurrency: int = 1,
) -> list[dict[str, Any]]:
    """Synchronous batch evaluation."""
    return asyncio.run(run_batch_async(scenarios, backend, concurrency=concurrency))
