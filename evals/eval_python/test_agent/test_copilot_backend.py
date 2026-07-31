"""Deterministic checks for Copilot backend session configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..copilot_backend import (
    CopilotAgentBackend,
    CopilotMCPBackEnd,
    create_copilot_backend,
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
