"""Pytest entry point for provider-backed red-team scenarios.

Requires the same opt-in environment and Copilot checks as the live agent
tests. The command-line runner remains available for repeated suites and
report output.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ..conftest import get_live_test_skip_reason
from ..copilot_backend import CopilotLLM
from ..copilot_llm import CopilotLLMJudge
from .redteam_adapter import (
    CopilotRedTeamEvaluator,
    run_redteam_suite,
    run_redteam_test,
)


class TestRedTeamScenarios:
    """Validate and execute configured red-team attacks."""

    def test_scenario_is_well_formed(self, security_scenario: dict[str, Any]) -> None:
        """Verify every red-team scenario has the fields the runner needs."""
        assert security_scenario["id"]
        assert security_scenario["prompt"]
        assert security_scenario["attack_type"]

    @pytest.mark.live
    @pytest.mark.skipif(
        get_live_test_skip_reason() is not None,
        reason=get_live_test_skip_reason() or "unknown reason",
    )
    def test_scenario_resists_attack(
        self, security_scenario: dict[str, Any]
    ) -> None:
        """Fail the live test when the independent judge finds a vulnerability."""
        backend = CopilotLLM(scenario_id=security_scenario["id"])
        judge = CopilotLLMJudge()

        def evaluator_factory(*, attack_type: str) -> CopilotRedTeamEvaluator:
            return CopilotRedTeamEvaluator(attack_type=attack_type, judge=judge)

        result = run_redteam_test(
            security_scenario,
            backend,
            evaluator_factory,
        )

        assert result["evaluation_status"] == "completed", result["reason"]
        assert not result["vulnerability_detected"], result["reason"]


def test_suite_preserves_detections_and_applies_severity_threshold() -> None:
    """Verify thresholded aggregates do not discard raw vulnerability evidence."""
    scenarios = [
        {"id": "low-attack", "prompt": "low", "attack_type": "low"},
        {"id": "critical-attack", "prompt": "critical", "attack_type": "critical"},
    ]
    severities = {"low": "low", "critical": "critical"}

    class StubBackend:
        def run(self, prompt: str) -> dict[str, Any]:
            return {"response": prompt, "tool_calls": []}

    class StubEvaluator:
        def __init__(self, *, attack_type: str) -> None:
            self.severity = severities[attack_type]

        def evaluate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                success=False,
                severity=self.severity,
                reason="stub vulnerability",
            )

    result = run_redteam_suite(
        scenarios,
        StubBackend(),
        StubEvaluator,
        repetitions=2,
        concurrency=2,
        severity_threshold="high",
    )

    assert result["total_runs"] == 4
    assert result["concurrency"] == 2
    assert result["severity_threshold"] == "high"
    assert result["summary"]["total_vulnerabilities_detected"] == 4
    assert result["summary"]["total_vulnerabilities_found"] == 2
