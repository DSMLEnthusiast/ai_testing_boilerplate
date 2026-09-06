"""Deterministic checks for Copilot backend session configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..copilot_backend import (
    CopilotAgentBackend,
    CopilotMCPBackEnd,
    _handle_math_permission_request,
    create_copilot_backend,
)
from ..copilot_llm import (
    CopilotLLMJudge,
    _deny_permission_request,
    _structured_json_candidates,
)
from ..trace import (
    AgentRunError,
    JudgeSchemaError,
    classify_tool_trace,
    require_successful_run,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_backend_factory_selects_mcp_or_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_BACKEND", "mcp")
    assert type(create_copilot_backend()) is CopilotMCPBackEnd

    monkeypatch.setenv("COPILOT_BACKEND", "agent")
    assert type(create_copilot_backend()) is CopilotAgentBackend


def test_backend_factory_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_BACKEND", "unknown")

    with pytest.raises(ValueError, match="COPILOT_BACKEND"):
        create_copilot_backend()


def test_agent_backend_loads_math_agents_and_mcp_tool_boundaries() -> None:
    backend = CopilotAgentBackend()

    config = backend._build_session_config(REPOSITORY_ROOT)
    agents = {agent["name"]: agent for agent in config["custom_agents"]}

    assert set(agents) == {
        "math-orchestrator",
        "math-unary-agent",
        "math-binary-agent",
    }
    assert agents["math-orchestrator"]["tools"] == ["agent"]
    assert agents["math-unary-agent"]["tools"] == [
        "math-mcp/exp",
        "math-mcp/log",
    ]
    assert agents["math-binary-agent"]["tools"] == [
        "math-mcp/add",
        "math-mcp/subtract",
        "math-mcp/multiply",
        "math-mcp/divide",
        "math-mcp/power",
    ]
    assert agents["math-unary-agent"]["model"] == "claude-haiku-4.5"
    assert config["mcp_servers"]["math-mcp"]["tools"] == ["*"]
    assert backend._prepare_prompt("calculate 2 + 2") == "@math-orchestrator\ncalculate 2 + 2"


def test_agent_backend_rejects_missing_orchestrator(tmp_path: Path) -> None:
    agent_file = tmp_path / "only-agent.agent.md"
    agent_file.write_text(
        "---\n"
        "name: only-agent\n"
        "description: A test agent\n"
        "tools: []\n"
        "---\n"
        "Do the test task.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Orchestrator agent"):
        CopilotAgentBackend(agents_directory=tmp_path)._build_session_config(
            REPOSITORY_ROOT
        )


def test_trace_is_partial_when_tool_events_do_not_match() -> None:
    assert classify_tool_trace([{"event_id": "pending"}], []) == "partial"
    assert classify_tool_trace([], ["orphaned"]) == "partial"
    assert classify_tool_trace([{"event_id": "done", "result": 4}], []) == "complete"


def test_failed_agent_run_is_rejected_before_evaluation() -> None:
    result = {
        "failure_category": "provider_error",
        "provider_error": "session failed",
        "response": "",
    }

    with pytest.raises(AgentRunError, match="session failed"):
        require_successful_run(result)


def test_permission_handlers_only_allow_math_mcp_requests() -> None:
    context: dict[str, str] = {}

    assert _handle_math_permission_request({"kind": "mcp"}, context)["kind"] == "approved"
    for kind in ("shell", "write", "read", "url", "unknown"):
        assert _handle_math_permission_request({"kind": kind}, context)["kind"] == "denied-by-rules"
    assert _deny_permission_request({"kind": "mcp"}, context)["kind"] == "denied-by-rules"


def test_structured_json_candidates_remove_fences_and_surrounding_text() -> None:
    candidates = _structured_json_candidates(
        'Here is the verdict:\n```json\n{"score": 1}\n```'
    )

    assert '{"score": 1}' in candidates


def test_judge_parser_accepts_json_surrounded_by_explanation() -> None:
    from pydantic import BaseModel

    class Verdict(BaseModel):
        score: int

    parsed = CopilotLLMJudge._parse_response(
        "The result is:\n```json\n{\"score\": 1}\n```",
        Verdict,
    )

    assert parsed.score == 1


def test_judge_parser_classifies_invalid_structured_output() -> None:
    from pydantic import BaseModel

    class Verdict(BaseModel):
        score: int

    with pytest.raises(JudgeSchemaError):
        CopilotLLMJudge._parse_response("not json", Verdict)
