"""DeepEval judge model backed by the Copilot SDK."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from .trace import JudgeSchemaError

try:
    from deepeval.models.base_model import DeepEvalBaseLLM
except ImportError:
    DeepEvalBaseLLM = object  # type: ignore[misc, assignment]


StructuredModel = TypeVar("StructuredModel")


def _deny_permission_request(_request: Any, _context: dict[str, str]) -> dict[str, Any]:
    return {"kind": "denied-by-rules", "rules": []}


class CopilotLLMJudge(DeepEvalBaseLLM):
    """DeepEval judge that sends evaluation prompts through Copilot SDK.

    The judge deliberately creates a session without MCP servers. This keeps
    the evaluator independent from the agent and its tools.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model_name = model or os.environ.get("COPILOT_JUDGE_MODEL") or os.environ.get(
            "COPILOT_MODEL", "gpt-5-mini"
        )
        self.timeout = timeout

    def load_model(self) -> None:
        """Load the model (Copilot clients are created per request)."""

    def get_model_name(self) -> str:
        """Return the configured judge model name."""
        return self.model_name

    def generate(
        self,
        prompt: str,
        schema: type[StructuredModel] | None = None,
        **kwargs: Any,
    ) -> str | StructuredModel:
        """Generate a text or structured judge response through Copilot SDK."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            text = asyncio.run(self.a_generate(prompt, schema=schema, **kwargs))
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                text = executor.submit(
                    asyncio.run, self.a_generate(prompt, schema=schema, **kwargs)
                ).result()

        return text

    async def a_generate(
        self,
        prompt: str,
        schema: type[StructuredModel] | None = None,
        **kwargs: Any,
    ) -> str | StructuredModel:
        """Generate a text or structured judge response asynchronously."""
        try:
            from copilot import CopilotClient
        except ImportError as error:
            raise RuntimeError(
                "Install github-copilot-sdk to use CopilotLLMJudge as a DeepEval judge"
            ) from error

        client = CopilotClient()
        started = asyncio.get_running_loop().time()

        def report_progress(stage: str) -> None:
            if os.environ.get("COPILOT_PROGRESS", "1") != "0":
                elapsed_ms = (asyncio.get_running_loop().time() - started) * 1000
                print(
                    f"[judge] model={self.model_name} stage={stage} "
                    f"elapsed_ms={elapsed_ms:.0f}",
                    flush=True,
                )

        report_progress("starting_client")
        await asyncio.wait_for(client.start(), timeout=self.timeout)
        report_progress("client_started")
        try:
            session = await asyncio.wait_for(
                client.create_session({
                    "model": self.model_name,
                    "on_permission_request": _deny_permission_request,
                }),
                timeout=self.timeout,
            )
            report_progress("session_created")
            response = await asyncio.wait_for(
                session.send_and_wait({"prompt": prompt}),
                timeout=self.timeout,
            )
            report_progress("response_received")
            text = self._response_text(response)
            return self._parse_response(text, schema)
        except asyncio.TimeoutError as error:
            report_progress("timeout")
            raise TimeoutError(
                f"Copilot judge request exceeded {self.timeout:.1f} seconds"
            ) from error
        finally:
            report_progress("stopping_client")
            await client.stop()
            report_progress("complete")

    @staticmethod
    def _response_text(response: Any) -> str:
        for value in (response, getattr(response, "data", response)):
            if isinstance(value, dict):
                for key in ("content", "text", "output"):
                    text = value.get(key)
                    if text is not None:
                        return str(text)
            for attribute in ("content", "text", "output"):
                text = getattr(value, attribute, None)
                if text is not None:
                    return str(text)
        return str(getattr(response, "data", response))

    @staticmethod
    def _parse_response(
        text: str,
        schema: type[StructuredModel] | None,
    ) -> str | StructuredModel:
        if schema is None:
            return text
        candidates = _structured_json_candidates(text)
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                if hasattr(schema, "model_validate_json"):
                    return schema.model_validate_json(candidate)  # type: ignore[attr-defined, no-any-return]
                if hasattr(schema, "parse_raw"):
                    return schema.parse_raw(candidate)  # type: ignore[attr-defined, no-any-return]
                raise TypeError(
                    "DeepEval structured output schema must be a Pydantic model"
                )
            except Exception as error:
                last_error = error
        raise JudgeSchemaError(
            f"Judge response did not match {getattr(schema, '__name__', schema)}: "
            f"{last_error}"
        ) from last_error


def _structured_json_candidates(text: str) -> list[str]:
    """Return likely JSON documents from a judge response, in priority order."""
    normalized = text.strip()
    candidates = [normalized]
    if normalized.startswith("```"):
        lines = normalized.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidates.insert(0, "\n".join(lines).strip())

    start = normalized.find("{")
    end = normalized.rfind("}")
    if start >= 0 and end > start:
        candidates.append(normalized[start : end + 1])

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique

