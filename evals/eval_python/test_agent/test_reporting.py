from __future__ import annotations

import pytest

from evals.eval_python.conftest import (
    _build_test_result,
    _classify_failure,
    _final_outcome,
    _safe_text,
)


def test_final_outcome_prioritizes_failure_over_other_phases() -> None:
    outcome, details = _final_outcome(
        [
            {"phase": "setup", "outcome": "passed"},
            {"phase": "call", "outcome": "failed", "details": "assertion failed"},
            {"phase": "teardown", "outcome": "passed"},
        ]
    )

    assert outcome == "failed"
    assert details == "assertion failed"


def test_final_outcome_preserves_skip_reason() -> None:
    outcome, details = _final_outcome(
        [{"phase": "setup", "outcome": "skipped", "details": "not configured"}]
    )

    assert outcome == "skipped"
    assert details == "not configured"


def test_build_test_result_sums_phase_durations() -> None:
    result = _build_test_result(
        "test_module.py::test_case",
        [
            {"phase": "setup", "outcome": "passed", "duration_seconds": 0.1},
            {"phase": "call", "outcome": "passed", "duration_seconds": 0.2},
            {"phase": "teardown", "outcome": "passed", "duration_seconds": 0.05},
        ],
    )

    assert result["nodeid"] == "test_module.py::test_case"
    assert result["outcome"] == "passed"
    assert result["duration_seconds"] == pytest.approx(0.35)


def test_safe_text_redacts_token_values(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TOKEN", "secret-token-value")

    sanitized = _safe_text("provider returned secret-token-value")

    assert sanitized == "provider returned [REDACTED]"
    assert "secret-token-value" not in sanitized


@pytest.mark.parametrize(
    ("details", "category"),
    [
        ("MissingTestCaseParamsError: tools_called cannot be None", "tool_trace_missing"),
        ("ValidationError for Verdicts", "judge_schema_error"),
        ("Session error: Failed to list models", "provider_error"),
        ("Agent run failed (agent_failure)", "agent_failure"),
        ("RUN_LLM_EVALS not set to '1'", "test_configuration_error"),
    ],
)
def test_classify_failure_for_review(details: str, category: str) -> None:
    assert _classify_failure(details) == category


def test_build_test_result_promotes_failure_category() -> None:
    result = _build_test_result(
        "test_module.py::test_case",
        [
            {
                "phase": "call",
                "outcome": "failed",
                "details": "JudgeSchemaError: invalid Verdicts payload",
                "failure_category": "judge_schema_error",
                "duration_seconds": 0.1,
            }
        ],
    )

    assert result["failure_category"] == "judge_schema_error"
