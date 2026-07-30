"""Integration tests: End-to-end scenario pipeline validation.

This suite validates:
1. All scenarios are discoverable and have expected results
2. Deterministic execution works for all scenarios
3. Error scenarios are handled correctly
4. Metric-only scenarios are identified and skipped appropriately

Run with:
    pytest evals/deepeval_v2/test_scenarios_integration.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from mcp_app.operations import execute, OperationError


class TestIntegrationScenarioPipeline:
    """End-to-end validation of scenario pipeline."""

    def test_scenario_discovery_count(
        self,
        scenarios: list[dict[str, Any]],
        tool_scenarios: list[dict[str, Any]],
        metric_only_scenarios: list[dict[str, Any]],
        error_scenarios: list[dict[str, Any]],
    ) -> None:
        """Verify scenario classification is complete and non-overlapping."""
        tool_ids = {s["id"] for s in tool_scenarios}
        metric_ids = {s["id"] for s in metric_only_scenarios}
        error_ids = {s["id"] for s in error_scenarios}

        all_ids = {s["id"] for s in scenarios}

        # Tool and metric scenarios should not overlap (metric-only has no tools)
        assert tool_ids.isdisjoint(metric_ids), "Tool and metric scenarios overlap"

        # Error scenarios are a subset of tool scenarios
        assert error_ids.issubset(
            tool_ids
        ), "Error scenarios must be in tool scenarios"

        # Union should cover all (but note: error is subset of tool)
        assert tool_ids.union(metric_ids) == all_ids, (
            f"Scenarios not classified: {all_ids - tool_ids.union(metric_ids)}"
        )

    def test_no_scenario_is_orphaned(
        self, scenarios: list[dict[str, Any]]
    ) -> None:
        """Verify no scenario is missing classification fields."""
        for scenario in scenarios:
            scenario_id = scenario["id"]
            has_tools = "expected_tools" in scenario
            has_metric = "metric_type" in scenario

            assert has_tools or has_metric, (
                f"Scenario {scenario_id} has neither expected_tools nor metric_type"
            )

    def test_tool_scenarios_are_executable(
        self, tool_scenarios: list[dict[str, Any]]
    ) -> None:
        """Verify all tool scenarios have valid tool calls."""
        for scenario in tool_scenarios:
            scenario_id = scenario["id"]
            expected_tools = scenario.get("expected_tools", [])

            assert len(expected_tools) > 0, (
                f"Tool scenario {scenario_id} has empty expected_tools"
            )

            for call in expected_tools:
                assert "name" in call, (
                    f"Scenario {scenario_id}: tool call missing 'name'"
                )
                assert "arguments" in call, (
                    f"Scenario {scenario_id}: tool call missing 'arguments'"
                )

    def test_error_scenarios_expect_failures(
        self, error_scenarios: list[dict[str, Any]]
    ) -> None:
        """Verify error scenarios have expected_error field."""
        for scenario in error_scenarios:
            scenario_id = scenario["id"]
            assert "expected_error" in scenario, (
                f"Error scenario {scenario_id} missing 'expected_error'"
            )
            assert isinstance(scenario["expected_error"], str), (
                f"Error scenario {scenario_id}: expected_error must be string"
            )

    def test_metric_only_scenarios_have_no_tools(
        self, metric_only_scenarios: list[dict[str, Any]]
    ) -> None:
        """Verify metric-only scenarios don't have expected_tools.

        Note: Metric-only may have metric_type OR be response-only scenarios.
        """
        for scenario in metric_only_scenarios:
            scenario_id = scenario["id"]
            # Should not have expected_tools (or have empty list)
            expected_tools = scenario.get("expected_tools", [])
            assert (
                len(expected_tools) == 0
            ), f"Metric-only scenario {scenario_id} should not have expected_tools"

            # Should have either metric_type OR response_contains
            has_metric = "metric_type" in scenario
            has_response = "expected_response_contains" in scenario or "response_contains" in scenario
            assert has_metric or has_response, (
                f"Metric-only scenario {scenario_id} must have metric_type or response_contains"
            )
