"""Compare normalized Python and .NET evaluation artifacts to golden scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPOSITORY_ROOT / "evals" / "golden" / "scenarios.json"
RESULT_SCHEMA_PATH = REPOSITORY_ROOT / "evals" / "golden" / "result-schema-v1.json"


def compare_result_to_scenario(
    result: dict[str, Any], scenario: dict[str, Any]
) -> list[str]:
    """Return contract mismatches for one normalized result record."""
    issues: list[str] = []
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(result), key=str)
    issues.extend(f"result schema: {error.message}" for error in schema_errors)

    scenario_id = scenario["id"]
    if result.get("scenario_id") != scenario_id:
        issues.append(
            f"scenario_id mismatch: expected {scenario_id!r}, "
            f"got {result.get('scenario_id')!r}"
        )

    expected_tools = scenario.get("expected_tools") or []
    actual_tools = result.get("tool_calls") or []
    if expected_tools:
        if result.get("trace_status") != "complete":
            issues.append(
                f"tool trace is {result.get('trace_status')!r}; "
                "expected complete trace"
            )
        elif len(actual_tools) != len(expected_tools):
            issues.append(
                f"tool count mismatch: expected {len(expected_tools)}, "
                f"got {len(actual_tools)}"
            )
        else:
            for index, (expected, actual) in enumerate(
                zip(expected_tools, actual_tools)
            ):
                expected_name = _canonical_tool_name(expected.get("name"))
                actual_name = _canonical_tool_name(actual.get("name"))
                if expected_name != actual_name:
                    issues.append(
                        f"tool {index} name mismatch: expected {expected_name!r}, "
                        f"got {actual_name!r}"
                    )
                if _canonical_json(expected.get("arguments", {})) != _canonical_json(
                    actual.get("arguments", {})
                ):
                    issues.append(f"tool {index} arguments mismatch")

    expected_error = scenario.get("expected_error")
    if expected_error:
        response = str(result.get("response", "")).lower()
        failure_category = str(result.get("failure_category") or "").lower()
        if expected_error.lower() not in response and expected_error.lower() not in failure_category:
            issues.append(f"expected error {expected_error!r} not represented")

    expected_response = scenario.get("expected_response")
    if expected_response and expected_response.lower() not in str(
        result.get("response", "")
    ).lower():
        issues.append("expected response not found")

    expected_contains = scenario.get("expected_response_contains")
    if expected_contains and expected_contains.lower() not in str(
        result.get("response", "")
    ).lower():
        issues.append("expected response substring not found")

    return issues


def load_results(path: Path) -> list[dict[str, Any]]:
    """Load either a result list or a red-team-style object with ``results``."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return payload["results"]
    raise ValueError(f"{path} must contain a result list or an object with results")


def validate_artifact(path: Path, scenarios: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validate every result record in one artifact and return a summary."""
    records = load_results(path)
    mismatches = []
    for result in records:
        scenario_id = result.get("scenario_id")
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            mismatches.append({"scenario_id": scenario_id, "issues": ["unknown scenario"]})
            continue
        issues = compare_result_to_scenario(result, scenario)
        if issues:
            mismatches.append({"scenario_id": scenario_id, "issues": issues})
    return {
        "artifact": str(path),
        "records": len(records),
        "mismatches": mismatches,
        "valid": not mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS_PATH)
    args = parser.parse_args()

    scenarios = {
        scenario["id"]: scenario
        for scenario in json.loads(args.scenarios.read_text(encoding="utf-8"))
    }
    summaries = [validate_artifact(path, scenarios) for path in args.results]
    print(json.dumps(summaries, indent=2))
    return 0 if all(summary["valid"] for summary in summaries) else 1


def _canonical_tool_name(name: Any) -> Any:
    if isinstance(name, str) and name.startswith("math-mcp-"):
        return name.removeprefix("math-mcp-")
    return name


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    sys.exit(main())
