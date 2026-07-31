"""Pytest entry point for provider-backed red-team scenarios.

Requires the same opt-in environment and Copilot checks as the live agent
tests. The command-line runner remains available for standalone repeated
suites and report output.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ..conftest import get_live_test_skip_reason
from ..copilot_backend import create_copilot_backend
from ..copilot_llm import CopilotLLMJudge
from .reporting import generate_html_report
from .tool_extractor import extract_tools_from_mcp, format_tools_for_context
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
        self,
        security_scenario: dict[str, Any],
        redteam_options: dict[str, Any],
    ) -> None:
        """Fail the live test when the independent judge finds a vulnerability."""
        if redteam_options["suite_mode"]:
            pytest.skip("red-team suite options are handled by the aggregate test")

        backend = create_copilot_backend(scenario_id=security_scenario["id"])
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

    @pytest.mark.live
    @pytest.mark.skipif(
        get_live_test_skip_reason() is not None,
        reason=get_live_test_skip_reason() or "unknown reason",
    )
    def test_redteam_suite_options(
        self,
        security_scenarios: list[dict[str, Any]],
        redteam_options: dict[str, Any],
    ) -> None:
        """Run repetitions and tool-aware generation through pytest options."""
        if not redteam_options["suite_mode"]:
            pytest.skip("use red-team options to enable aggregate suite mode")

        tools_context = None
        tools_info = None
        if redteam_options["tool_aware"]:
            tools_info = extract_tools_from_mcp()
            tools_context = format_tools_for_context(tools_info)

        def backend_factory():
            return create_copilot_backend()

        def evaluator_factory(*, attack_type: str) -> CopilotRedTeamEvaluator:
            return CopilotRedTeamEvaluator(
                attack_type=attack_type,
                judge=CopilotLLMJudge(),
            )

        result = run_redteam_suite(
            security_scenarios,
            backend_factory,
            evaluator_factory,
            attack_types=redteam_options["attack_types"],
            repetitions=redteam_options["repetitions"],
            concurrency=redteam_options["concurrency"],
            severity_threshold=redteam_options["severity_threshold"],
            tools_context=tools_context,
            tools_info=tools_info,
        )

        assert result["summary"]["total_evaluation_failures"] == 0
        assert result["summary"]["total_vulnerabilities_detected"] == 0


def test_suite_preserves_detections_and_applies_severity_threshold() -> None:
    """Verify thresholded aggregates do not discard raw vulnerability evidence."""
    scenarios = [
        {"id": "low-attack", "prompt": "low", "attack_type": "low"},
        {"id": "critical-attack", "prompt": "critical", "attack_type": "critical"},
    ]
    severities = {"low": "low", "critical": "critical"}

    class StubBackend:
        instances = 0

        def __init__(self) -> None:
            StubBackend.instances += 1

        def run(self, prompt: str) -> dict[str, Any]:
            return {"response": prompt, "tool_calls": []}

    class StubEvaluator:
        instances = 0

        def __init__(self, *, attack_type: str) -> None:
            StubEvaluator.instances += 1
            self.severity = severities[attack_type]

        def evaluate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                success=False,
                severity=self.severity,
                reason="stub vulnerability",
            )

    result = run_redteam_suite(
        scenarios,
        StubBackend,
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
    assert StubBackend.instances == 4
    assert StubEvaluator.instances == 4


def test_provider_failure_is_not_sent_to_redteam_judge() -> None:
    class FailedBackend:
        def run(self, _prompt: str) -> dict[str, Any]:
            return {
                "response": "",
                "failure_category": "provider_error",
                "provider_error": "session unavailable",
            }

    class UnexpectedEvaluator:
        def __init__(self, *, attack_type: str) -> None:
            pytest.fail(f"judge created for failed {attack_type} run")

    result = run_redteam_test(
        {"id": "provider-failure", "prompt": "test", "attack_type": "availability"},
        FailedBackend(),
        UnexpectedEvaluator,
    )

    assert result["evaluation_status"] == "failed"
    assert result["failure_category"] == "provider_error"
    assert result["vulnerability_detected"] is False


def test_html_report_escapes_dynamic_labels() -> None:
    hostile_label = '<script>alert("unsafe")</script>'
    report = generate_html_report(
        {
            "framework": hostile_label,
            "framework_version": hostile_label,
            "summary": {},
            "by_attack_type": {
                hostile_label: {
                    "attack_count": 1,
                    "vulnerabilities_found": 0,
                    "vulnerability_rate": 0.0,
                    "defense_rate": 1.0,
                    "avg_latency_ms": 1.0,
                }
            },
        }
    )

    assert hostile_label not in report
    assert "&lt;script&gt;" in report
