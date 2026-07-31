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
JUDGE_RUBRICS_PATH = REPO_ROOT / "evals" / "golden" / "judge-rubrics.json"
REDTEAM_SEVERITIES = ("critical", "high", "medium", "low", "info")


def positive_int(value: str) -> int:
    """Parse a strictly positive pytest option value."""
    parsed = int(value)
    if parsed < 1:
        raise pytest.UsageError("red-team numeric options must be at least 1")
    return parsed


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


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register optional red-team suite controls for pytest runs."""
    group = parser.getgroup("red-team")
    group.addoption(
        "--redteam-repetitions",
        type=positive_int,
        default=positive_int(os.environ.get("REDTEAM_REPETITIONS", "1")),
        help="Run each red-team scenario this many times.",
    )
    group.addoption(
        "--redteam-concurrency",
        type=positive_int,
        default=positive_int(os.environ.get("REDTEAM_CONCURRENCY", "1")),
        help="Maximum concurrent red-team scenario runs.",
    )
    group.addoption(
        "--redteam-tool-aware",
        action="store_true",
        default=os.environ.get("REDTEAM_TOOL_AWARE") == "1",
        help="Generate additional attacks informed by MCP tool descriptions.",
    )
    group.addoption(
        "--redteam-attack-types",
        nargs="+",
        default=None,
        help="Limit the suite to attack types such as prompt_injection or jailbreak.",
    )
    group.addoption(
        "--redteam-severity-threshold",
        choices=REDTEAM_SEVERITIES,
        default=os.environ.get("REDTEAM_SEVERITY_THRESHOLD", "low"),
        help="Minimum severity included in red-team aggregate reporting.",
    )


@pytest.fixture(scope="session")
def scenarios() -> list[dict[str, Any]]:
    """Load all test scenarios from the shared fixture."""
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


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


@pytest.fixture(scope="session")
def redteam_options(pytestconfig: pytest.Config) -> dict[str, Any]:
    """Expose red-team CLI and environment settings to pytest tests."""
    repetitions = pytestconfig.getoption("--redteam-repetitions")
    concurrency = pytestconfig.getoption("--redteam-concurrency")
    tool_aware = pytestconfig.getoption("--redteam-tool-aware")
    attack_types = pytestconfig.getoption("--redteam-attack-types")
    severity_threshold = pytestconfig.getoption("--redteam-severity-threshold")
    return {
        "repetitions": repetitions,
        "concurrency": concurrency,
        "tool_aware": tool_aware,
        "attack_types": attack_types,
        "severity_threshold": severity_threshold,
        "suite_mode": (
            repetitions != 1
            or concurrency != 1
            or tool_aware
            or attack_types is not None
            or severity_threshold != "low"
        ),
    }


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
