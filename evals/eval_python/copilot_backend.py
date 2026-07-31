"""Copilot SDK LLM backend for agent evaluation."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from .trace import classify_tool_trace


def _handle_math_permission_request(
    request: Any, _context: dict[str, str]
) -> dict[str, Any]:
    if isinstance(request, dict) and request.get("kind") == "mcp":
        return {"kind": "approved", "rules": []}
    return {"kind": "denied-by-rules", "rules": []}


def _canonical_tool_name(name: Any) -> Any:
    if isinstance(name, str) and name.startswith("math-mcp-"):
        return name.removeprefix("math-mcp-")
    return name


def _load_agent_configs(agents_directory: Path) -> list[dict[str, Any]]:
    """Load Copilot custom-agent configurations from ``*.agent.md`` files."""
    if not agents_directory.is_dir():
        raise FileNotFoundError(f"Custom-agent directory does not exist: {agents_directory}")

    agent_files = sorted(agents_directory.glob("*.agent.md"))
    if not agent_files:
        raise FileNotFoundError(f"No custom-agent files found in: {agents_directory}")

    configs: list[dict[str, Any]] = []
    for agent_file in agent_files:
        lines = agent_file.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError(f"Missing YAML frontmatter in custom-agent file: {agent_file}")

        try:
            closing_marker = lines.index("---", 1)
        except ValueError as error:
            raise ValueError(
                f"Unterminated YAML frontmatter in custom-agent file: {agent_file}"
            ) from error

        metadata = yaml.safe_load("\n".join(lines[1:closing_marker]))
        if not isinstance(metadata, dict):
            raise ValueError(f"Agent frontmatter must be a mapping: {agent_file}")

        name = metadata.get("name")
        description = metadata.get("description")
        prompt = "\n".join(lines[closing_marker + 1 :]).strip()
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Agent frontmatter needs a non-empty name: {agent_file}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"Agent frontmatter needs a non-empty description: {agent_file}"
            )
        if not prompt:
            raise ValueError(f"Agent file needs a non-empty prompt: {agent_file}")

        tools = metadata.get("tools", [])
        if tools is None:
            tools = []
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            raise ValueError(f"Agent tools must be a list of strings: {agent_file}")

        config: dict[str, Any] = {
            "name": name,
            "display_name": name,
            "description": description,
            "tools": tools,
            "prompt": prompt,
        }
        model = metadata.get("model")
        if model is not None:
            if not isinstance(model, str) or not model.strip():
                raise ValueError(f"Agent model must be a non-empty string: {agent_file}")
            config["model"] = model
        if isinstance(metadata.get("infer"), bool):
            config["infer"] = metadata["infer"]
        configs.append(config)

    return configs


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


class CopilotMCPBackEnd(BaseLLM):
    """Run a prompt through Copilot SDK with the shared MCP server attached."""

    def __init__(self, **session_options: Any) -> None:
        self.session_options = session_options

    def _prepare_prompt(self, prompt: str) -> str:
        return prompt

    def _build_session_config(self, root: Path) -> dict[str, Any]:
        return {
            "model": self.session_options.get(
                "model", os.environ.get("COPILOT_MODEL", "gpt-5-mini")
            ),
            "on_permission_request": _handle_math_permission_request,
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
        }

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
        unsubscribe = None
        tool_calls = []
        tool_calls_by_id: dict[str, dict[str, Any]] = {}
        tool_results = []
        unmatched_event_ids: list[str] = []
        response_text = ""
        usage = {}
        trace_status = "unavailable"
        provider_error = None
        failure_category = None

        try:
            await client.start()
            client_started = True
            session = await client.create_session(self._build_session_config(root))

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
                        unmatched_event_ids.append(tool_call_id)
                        return
                    result = getattr(data, "result", None)
                    tool_call["result"] = getattr(result, "content", result)

            unsubscribe = session.on(handle_event)
            response = await session.send_and_wait({"prompt": self._prepare_prompt(prompt)})

            # Extract response content
            if hasattr(response.data, "content"):
                response_text = response.data.content
            elif hasattr(response.data, "text"):
                response_text = response.data.text
            else:
                response_text = str(response.data)

            tool_calls = list(tool_calls_by_id.values())
            tool_results = [call.get("result") for call in tool_calls if "result" in call]
            trace_status = classify_tool_trace(tool_calls, unmatched_event_ids)

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
            cleanup_errors = []
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception as error:
                    cleanup_errors.append(f"event unsubscribe failed: {error}")
            if client_started:
                try:
                    await client.stop()
                except Exception as error:
                    cleanup_errors.append(f"client stop failed: {error}")
            if cleanup_errors:
                cleanup_detail = "; ".join(cleanup_errors)
                provider_error = "; ".join(
                    detail for detail in (provider_error, cleanup_detail) if detail
                )
                failure_category = "provider_error"
                trace_status = "provider_error"

        latency_ms = (time.perf_counter() - started) * 1000

        return {
            "schema_version": "1.0",
            "response": response_text,
            "scenario_id": self.session_options.get("scenario_id"),
            "agent_runtime": "copilot-sdk",
            "model_provider": "copilot",
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "trace_status": trace_status,
            "unmatched_event_ids": unmatched_event_ids,
            "provider_error": provider_error,
            "failure_category": failure_category,
            "usage": usage,
            "latency_ms": latency_ms,
        }


class CopilotAgentBackend(CopilotMCPBackEnd):
    """Run prompts with repository custom agents and their MCP tools loaded."""

    def __init__(
        self,
        agents_directory: str | Path | None = None,
        **session_options: Any,
    ) -> None:
        super().__init__(**session_options)
        self.agents_directory = (
            Path(agents_directory) if agents_directory is not None else None
        )
        self.orchestrator_name = "math-orchestrator"

    def _build_session_config(self, root: Path) -> dict[str, Any]:
        config = super()._build_session_config(root)
        agents_directory = self.agents_directory or root / ".github" / "agents" / "math_agent"
        custom_agents = _load_agent_configs(agents_directory)
        if self.orchestrator_name not in {agent["name"] for agent in custom_agents}:
            raise ValueError(
                f"Orchestrator agent {self.orchestrator_name!r} was not found in {agents_directory}"
            )
        config["custom_agents"] = custom_agents
        return config

    def _prepare_prompt(self, prompt: str) -> str:
        return f"@{self.orchestrator_name}\n{prompt}"


def create_copilot_backend(**session_options: Any) -> CopilotMCPBackEnd:
    """Create the live-test backend selected by ``COPILOT_BACKEND``."""
    backend_name = os.environ.get("COPILOT_BACKEND", "mcp").strip().lower()
    if backend_name == "mcp":
        return CopilotMCPBackEnd(**session_options)
    if backend_name == "agent":
        return CopilotAgentBackend(**session_options)
    raise ValueError(
        "COPILOT_BACKEND must be 'mcp' or 'agent', "
        f"not {backend_name!r}"
    )


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
