"""Deterministic scenario tests (no API required, always run, fast feedback).

This suite:
1. Validates scenario schema integrity
2. Verifies expected results exist in fixtures
3. Executes scenarios locally using operations.execute()
4. Validates results match expected outcomes
5. Handles error scenarios explicitly

Run with:
    pytest evals/deepeval_v2/test_scenarios_deterministic.py -v
"""

from __future__ import annotations

import json
import math
from typing import Any

import pytest

from mcp_app.operations import OperationError, execute


class TestScenarioFixtures:
    """Validate scenario schema and structure."""

    def test_scenario_has_required_fields(self, scenario: dict[str, Any]) -> None:
        """Verify scenario has required fields."""
        assert "id" in scenario, "Scenario missing 'id'"
        assert "prompt" in scenario, "Scenario missing 'prompt'"
        # Either has expected_tools or metric_type
        has_tools = "expected_tools" in scenario
        has_metric = "metric_type" in scenario
        assert has_tools or has_metric, "Scenario needs expected_tools or metric_type"

    def test_scenario_expected_tools_valid(self, scenario: dict[str, Any]) -> None:
        """Verify expected_tools format if present."""
        if not scenario.get("expected_tools"):
            pytest.skip("metric-only scenario")

        for call in scenario["expected_tools"]:
            assert "name" in call, f"Tool call missing 'name': {call}"
            assert "arguments" in call, f"Tool call missing 'arguments': {call}"


class TestScenarioExpectations:
    """Verify expected results exist and match scenario."""

    def test_scenario_has_expected_result(
        self, scenario: dict[str, Any], expected_results: dict[str, Any]
    ) -> None:
        """Verify expected result exists for this scenario."""
        scenario_id = scenario["id"]
        assert (
            scenario_id in expected_results
        ), f"No expected result for scenario {scenario_id}"

    def test_expected_result_shape(
        self, scenario: dict[str, Any], expected_results: dict[str, Any]
    ) -> None:
        """Verify expected result has valid shape."""
        scenario_id = scenario["id"]
        expected = expected_results[scenario_id]

        # Check for response-only scenarios (no tools, just response validation)
        if "response_contains" in expected:
            assert isinstance(expected["response_contains"], str), (
                "response_contains must be string"
            )
            return  # Response-only scenario

        # Must be either {"value": ..., "operation": ...} or {"error": ...}
        if "error" in expected:
            assert isinstance(expected["error"], str), "error must be string"
            # Should not have both error and value
            assert (
                "value" not in expected
            ), "Cannot have both error and value"
        else:
            # Tool-based scenario should have value
            assert "value" in expected or "operation" in expected, (
                f"Expected result for {scenario_id} must have value or operation"
            )


class TestScenarioMockExecution:
    """Execute scenarios locally and validate results."""

    def test_scenario_expected_tools_execute_successfully(
        self, scenario: dict[str, Any], expected_results: dict[str, Any]
    ) -> None:
        """Execute expected_tools and verify result matches expected."""
        if not scenario.get("expected_tools"):
            pytest.skip("metric-only scenario")

        scenario_id = scenario["id"]
        expected = expected_results[scenario_id]
        expected_tools = scenario["expected_tools"]

        # If we expect an error, the operation should fail
        if "error" in expected:
            # Try to execute and expect the operation to raise an error
            for call in expected_tools:
                try:
                    result = execute(call["name"], call.get("arguments", {}))
                    # If we got here without error, the test fails
                    pytest.fail(
                        f"Expected error {expected['error']} but got result: {result}"
                    )
                except OperationError as e:
                    # Verify error category matches
                    assert e.category == expected["error"], (
                        f"Expected {expected['error']}, got {e.category}"
                    )
                    return  # Success: got expected error
        else:
            # Execute all tools and verify final result
            result = None
            for call in expected_tools:
                result = execute(call["name"], call.get("arguments", {}))

            # Verify result matches expected
            if result is not None:
                actual_value = result.get("value")
                expected_value = expected.get("value")

                # Use numerical tolerance for floating-point comparisons
                if isinstance(actual_value, (int, float)) and isinstance(
                    expected_value, (int, float)
                ):
                    assert math.isclose(
                        actual_value, expected_value, rel_tol=1e-9, abs_tol=1e-9
                    ), (
                        f"Result mismatch: expected {expected_value}, "
                        f"got {actual_value}"
                    )
                else:
                    assert actual_value == expected_value, (
                        f"Result mismatch: expected {expected_value}, "
                        f"got {actual_value}"
                    )

    def test_scenario_error_handling(
        self, scenario: dict[str, Any], expected_results: dict[str, Any]
    ) -> None:
        """Verify error scenarios produce expected failure_category."""
        if not scenario.get("expected_error"):
            pytest.skip("not an error scenario")

        scenario_id = scenario["id"]
        expected_error = scenario["expected_error"]
        expected_tools = scenario.get("expected_tools", [])

        assert (
            len(expected_tools) > 0
        ), f"Error scenario {scenario_id} has no tools to execute"

        # Try each tool call and verify error matches
        for call in expected_tools:
            try:
                execute(call["name"], call.get("arguments", {}))
                pytest.fail(
                    f"Expected error {expected_error} for {scenario_id} "
                    f"but operation succeeded"
                )
            except OperationError as e:
                assert e.category == expected_error, (
                    f"Scenario {scenario_id}: expected {expected_error}, "
                    f"got {e.category}"
                )
