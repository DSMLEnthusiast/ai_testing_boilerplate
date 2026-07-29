"""DeepEval judge model backed by the Copilot SDK."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

try:
    from deepeval.models.base_model import DeepEvalBaseLLM
except ImportError:
    DeepEvalBaseLLM = object  # type: ignore[misc, assignment]


StructuredModel = TypeVar("StructuredModel")


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
            "COPILOT_MODEL", "gpt-4o"
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
            text = asyncio.run(self.a_generate(prompt, **kwargs))
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                text = executor.submit(
                    asyncio.run, self.a_generate(prompt, **kwargs)
                ).result()

        return self._parse_response(text, schema)

    async def a_generate(
        self,
        prompt: str,
        schema: type[StructuredModel] | None = None,
        **kwargs: Any,
    ) -> str | StructuredModel:
        """Generate a text or structured judge response asynchronously."""
        try:
            from copilot import CopilotClient
            from copilot.session import PermissionHandler
        except ImportError as error:
            raise RuntimeError(
                "Install github-copilot-sdk to use CopilotLLMJudge as a DeepEval judge"
            ) from error

        client = CopilotClient()
        await asyncio.wait_for(client.start(), timeout=self.timeout)
        try:
            session = await asyncio.wait_for(
                client.create_session(
                    model=self.model_name,
                    on_permission_request=PermissionHandler.approve_all,
                ),
                timeout=self.timeout,
            )
            response = await asyncio.wait_for(
                session.send_and_wait(prompt),
                timeout=self.timeout,
            )
            text = self._response_text(response)
            return self._parse_response(text, schema)
        except asyncio.TimeoutError as error:
            raise TimeoutError(
                f"Copilot judge request exceeded {self.timeout:.1f} seconds"
            ) from error
        finally:
            await client.stop()

    @staticmethod
    def _response_text(response: Any) -> str:
        data = response.data
        if hasattr(data, "content"):
            return str(data.content)
        if hasattr(data, "text"):
            return str(data.text)
        return str(data)

    @staticmethod
    def _parse_response(
        text: str,
        schema: type[StructuredModel] | None,
    ) -> str | StructuredModel:
        if schema is None:
            return text
        if hasattr(schema, "model_validate_json"):
            return schema.model_validate_json(text)  # type: ignore[attr-defined, no-any-return]
        if hasattr(schema, "parse_raw"):
            return schema.parse_raw(text)  # type: ignore[attr-defined, no-any-return]
        raise TypeError("DeepEval structured output schema must be a Pydantic model")

