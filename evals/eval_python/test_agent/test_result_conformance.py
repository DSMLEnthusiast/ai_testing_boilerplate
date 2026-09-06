from __future__ import annotations

from evals.eval_python.result_conformance import compare_result_to_scenario


def test_conformance_accepts_complete_tool_contract() -> None:
    scenario = {
        "id": "add-basic",
        "prompt": "add",
        "target_boundary": "agent",
        "rubric_id": "math-tool-v1",
        "expected_tools": [{"name": "add", "arguments": {"a": 2, "b": 3}}],
    }
    result = {
        "schema_version": "1.0",
        "scenario_id": "add-basic",
        "agent_runtime": "copilot-sdk",
        "model_provider": "copilot",
        "failure_category": None,
        "latency_ms": 1.0,
        "trace_status": "complete",
        "tool_calls": [{"name": "math-mcp-add", "arguments": {"b": 3, "a": 2}}],
    }

    assert compare_result_to_scenario(result, scenario) == []


def test_conformance_reports_missing_trace() -> None:
    scenario = {
        "id": "add-basic",
        "prompt": "add",
        "target_boundary": "agent",
        "rubric_id": "math-tool-v1",
        "expected_tools": [{"name": "add", "arguments": {"a": 2, "b": 3}}],
    }
    result = {
        "schema_version": "1.0",
        "scenario_id": "add-basic",
        "agent_runtime": "copilot-sdk-dotnet",
        "model_provider": "copilot",
        "failure_category": "tool_trace_missing",
        "latency_ms": 1.0,
        "trace_status": "unavailable",
        "tool_calls": [],
    }

    assert any("trace is 'unavailable'" in issue for issue in compare_result_to_scenario(result, scenario))
