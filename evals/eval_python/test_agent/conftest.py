"""Shared fixtures and parametrization for all scenario tests.

This module:
- Loads scenarios and expected results from fixtures
- Parametrizes all test classes with scenario IDs
- Groups scenarios by type for selective testing
- Validates Copilot SDK and authentication for live tests
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

# Fixture loading resolves from test_agent/ subfolder, so parents[1] is eval_python


def is_sdk_installed() -> bool:
    """Check if Copilot SDK is installed and importable."""
    try:
        import copilot  # noqa: F401
        return True
    except ImportError:
        return False


def is_cli_available() -> bool:
    """Check if copilot CLI is available in PATH."""
    try:
        result = subprocess.run(
            ["copilot", "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_auth_configured() -> bool:
    """Check if authentication is configured via env vars or cached."""
    # Check for explicit token in environment
    if os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return True
    # Check for cached authentication (Copilot CLI stores auth locally)
    # This is a best-effort check; the CLI may still fail if token is invalid
    return os.path.exists(os.path.expanduser("~/.copilot/config.json")) or os.path.exists(
        os.path.expanduser("~/.github/copilot_cli/config.json")
    )


def get_live_test_skip_reason() -> str | None:
    """Return skip reason if live tests should be skipped, None otherwise."""
    if os.environ.get("RUN_LLM_EVALS") != "1":
        return "RUN_LLM_EVALS not set to '1'"
    if not is_sdk_installed():
        return "Copilot SDK not installed (install: pip install github-copilot-sdk)"
    if not is_cli_available():
        return "copilot CLI not available in PATH (bundled with SDK, check installation)"
    if not is_auth_configured():
        return "No authentication configured (set COPILOT_GITHUB_TOKEN or run 'copilot auth login')"
    return None


@pytest.fixture(scope="session")
def scenarios() -> list[dict[str, Any]]:
    """Load all test scenarios from evals/golden/scenarios.json."""
    # Path: evals/eval_python/test_agent/conftest.py
    # parents[0] = test_agent, parents[1] = eval_python, parents[2] = evals, parents[3] = ai_test_boilerplate
    root = Path(__file__).resolve().parents[3]
    scenarios_path = root / "evals" / "golden" / "scenarios.json"
    if not scenarios_path.exists():
        # Fallback: might be running from subdirectory
        scenarios_path = Path(__file__).resolve().parents[4] / "evals" / "golden" / "scenarios.json"
    return json.loads(scenarios_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def expected_results() -> dict[str, Any]:
    """Load expected results from evals/golden/expected-results.json."""
    root = Path(__file__).resolve().parents[3]
    expected_path = root / "evals" / "golden" / "expected-results.json"
    if not expected_path.exists():
        # Fallback: might be running from subdirectory
        expected_path = Path(__file__).resolve().parents[4] / "evals" / "golden" / "expected-results.json"
    return json.loads(expected_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def judge_rubrics() -> dict[str, Any]:
    """Load judge rubrics from evals/golden/judge-rubrics.json."""
    root = Path(__file__).resolve().parents[3]
    rubrics_path = root / "evals" / "golden" / "judge-rubrics.json"
    if not rubrics_path.exists():
        # Fallback: might be running from subdirectory
        rubrics_path = Path(__file__).resolve().parents[4] / "evals" / "golden" / "judge-rubrics.json"
    return json.loads(rubrics_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def tool_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that have expected_tools (tool-based, not metric-only)."""
    return [s for s in scenarios if s.get("expected_tools")]


@pytest.fixture(scope="session")
def metric_only_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that are metric-only (no expected_tools)."""
    return [s for s in scenarios if not s.get("expected_tools")]


@pytest.fixture(scope="session")
def error_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that expect errors (expected_error field)."""
    return [s for s in scenarios if s.get("expected_error")]


@pytest.fixture(scope="session")
def security_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios with attack_type (security/red-team scenarios)."""
    return [s for s in scenarios if s.get("attack_type")]


def pytest_generate_tests(metafunc: Any) -> None:
    """Parametrize tests with scenario IDs.

    Any test with a 'scenario' parameter will be run once per scenario ID.
    Test IDs will be the scenario ID for easy filtering.
    """
    if "scenario" in metafunc.fixturenames:
        # Path: evals/eval_python/test_agent/conftest.py -> up 3 levels to repo root
        root = Path(__file__).resolve().parents[3]
        scenarios_path = root / "evals" / "golden" / "scenarios.json"
        if not scenarios_path.exists():
            # Fallback: might be running from subdirectory
            scenarios_path = Path(__file__).resolve().parents[4] / "evals" / "golden" / "scenarios.json"
        scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))

        # Parametrize with full scenario dict, using scenario ID as test ID
        metafunc.parametrize(
            "scenario",
            scenarios,
            ids=[s["id"] for s in scenarios],
        )
