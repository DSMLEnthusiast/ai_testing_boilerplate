"""Shared fixtures and parametrization for Python evaluation suites."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO_ROOT / "evals" / "golden" / "scenarios.json"
EXPECTED_RESULTS_PATH = REPO_ROOT / "evals" / "golden" / "expected-results.json"
JUDGE_RUBRICS_PATH = REPO_ROOT / "evals" / "golden" / "judge-rubrics.json"


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
    if any(
        os.environ.get(name)
        for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
    ):
        return True
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
    """Load all test scenarios from the shared fixture."""
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def expected_results() -> dict[str, Any]:
    """Load expected results from the shared fixture."""
    return json.loads(EXPECTED_RESULTS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def judge_rubrics() -> dict[str, Any]:
    """Load judge rubrics from the shared fixture."""
    return json.loads(JUDGE_RUBRICS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def tool_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that have expected tool calls."""
    return [scenario for scenario in scenarios if scenario.get("expected_tools")]


@pytest.fixture(scope="session")
def metric_only_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that do not have expected tool calls."""
    return [scenario for scenario in scenarios if not scenario.get("expected_tools")]


@pytest.fixture(scope="session")
def error_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that expect operation errors."""
    return [scenario for scenario in scenarios if scenario.get("expected_error")]


@pytest.fixture(scope="session")
def security_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter scenarios that define a red-team attack type."""
    return [scenario for scenario in scenarios if scenario.get("attack_type")]


def pytest_generate_tests(metafunc: Any) -> None:
    """Parametrize scenario fixtures with stable scenario IDs."""
    if "scenario" in metafunc.fixturenames:
        scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        metafunc.parametrize("scenario", scenarios, ids=[s["id"] for s in scenarios])
    if "security_scenario" in metafunc.fixturenames:
        scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        security_scenarios = [s for s in scenarios if s.get("attack_type")]
        metafunc.parametrize(
            "security_scenario",
            security_scenarios,
            ids=[s["id"] for s in security_scenarios],
        )
