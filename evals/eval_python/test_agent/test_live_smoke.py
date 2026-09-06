"""Explicit live preflight for the agent, MCP trace, and judge model."""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from ..conftest import get_live_test_skip_reason
from ..copilot_backend import create_copilot_backend
from ..copilot_llm import CopilotLLMJudge
from ..trace import require_expected_tool_trace, require_successful_run


class SmokeVerdict(BaseModel):
    ok: bool


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LLM_SMOKE") != "1",
    reason="RUN_LLM_SMOKE is not set to '1'",
)


def test_live_agent_and_judge_smoke() -> None:
    """Verify credentials, model availability, MCP startup, and judge parsing."""
    skip_reason = get_live_test_skip_reason()
    if skip_reason:
        pytest.skip(skip_reason)

    backend = create_copilot_backend(scenario_id="live-smoke")
    result = dict(
        require_successful_run(
            backend.run("Use the math MCP add tool to calculate 2 plus 3.")
        )
    )
    tool_calls = require_expected_tool_trace(
        result,
        [{"name": "add", "arguments": {"a": 2, "b": 3}}],
    )

    assert tool_calls[0]["name"] == "add"
    assert result["trace_status"] == "complete"

    verdict = CopilotLLMJudge().generate(
        'Return exactly JSON with one boolean field: {"ok": true}.',
        schema=SmokeVerdict,
    )
    assert isinstance(verdict, SmokeVerdict)
    assert verdict.ok is True
