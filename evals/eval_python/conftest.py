"""Shared fixtures and parametrization for Python evaluation suites."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO_ROOT / "evals" / "golden" / "scenarios.json"
JUDGE_RUBRICS_PATH = REPO_ROOT / "evals" / "golden" / "judge-rubrics.json"
REDTEAM_SEVERITIES = ("critical", "high", "medium", "low", "info")
RESULTS_ENV_VAR = "PYTEST_RESULTS_JSON"
DEFAULT_RESULTS_PATH = "test-results/pytest-results.json"
_SECRET_PATTERN = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,})"
)
_REPORT_CONFIG: pytest.Config | None = None


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
    reporting_group = parser.getgroup("test reporting")
    reporting_group.addoption(
        "--test-results-json",
        action="store",
        default=os.environ.get(RESULTS_ENV_VAR, DEFAULT_RESULTS_PATH),
        help=f"Write a post-run JSON report (default: {DEFAULT_RESULTS_PATH}).",
    )
    reporting_group.addoption(
        "--no-test-results",
        action="store_true",
        help="Disable the post-run JSON report.",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    secret_values = [
        value
        for name, value in os.environ.items()
        if any(part in name.upper() for part in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))
        and value
    ]
    for secret in sorted(secret_values, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return _SECRET_PATTERN.sub("[REDACTED]", text)


def _report_path(config: pytest.Config) -> Path | None:
    if config.getoption("--no-test-results"):
        return None
    configured_path = config.getoption("--test-results-json")
    if not configured_path:
        return None
    path = Path(configured_path)
    return path if path.is_absolute() else Path.cwd() / path


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    commit = result.stdout.strip()
    return commit or None


def _phase_record(report: pytest.TestReport) -> dict[str, Any]:
    record: dict[str, Any] = {
        "phase": report.when,
        "outcome": report.outcome,
        "duration_seconds": report.duration,
    }
    if getattr(report, "wasxfail", None):
        record["wasxfail"] = report.wasxfail
    if report.longrepr is not None:
        details = _safe_text(report.longrepr)
        record["details"] = details
        if report.outcome == "failed":
            category = _classify_failure(details)
            if category:
                record["failure_category"] = category
    return record


def _classify_failure(details: str | None) -> str | None:
    """Map common live-test failures to stable review categories."""
    if not details:
        return None
    normalized = details.lower()
    if "tool trace" in normalized or "tools_called" in normalized:
        return "tool_trace_missing"
    if (
        "judgeschemaerror" in normalized
        or "judge schema error" in normalized
        or "validationerror" in normalized
        or "verdicts" in normalized
        or "pydantic" in normalized
        or "structured output" in normalized
    ):
        return "judge_schema_error"
    if (
        "failed to list models" in normalized
        or "provider_error" in normalized
        or "copilot" in normalized
        or "session error" in normalized
        or "timeout" in normalized
    ):
        return "provider_error"
    if (
        "run_llm_evals" in normalized
        or "sdk not installed" in normalized
        or "authentication configured" in normalized
    ):
        return "test_configuration_error"
    if "agent run failed" in normalized or "agent_failure" in normalized:
        return "agent_failure"
    return "evaluation_error"


def _final_outcome(phases: list[dict[str, Any]]) -> tuple[str, str | None]:
    for phase in phases:
        if phase["outcome"] == "failed":
            return "failed", phase.get("details")
    for phase in phases:
        if phase.get("wasxfail") and phase["outcome"] == "passed":
            return "xpassed", phase.get("details")
    for phase in phases:
        if phase.get("wasxfail") and phase["outcome"] == "skipped":
            return "xfailed", phase.get("details")
    for phase in phases:
        if phase["outcome"] == "skipped":
            return "skipped", phase.get("details")
    return "passed", None


def _build_test_result(nodeid: str, phases: list[dict[str, Any]]) -> dict[str, Any]:
    outcome, details = _final_outcome(phases)
    result: dict[str, Any] = {
        "nodeid": nodeid,
        "outcome": outcome,
        "duration_seconds": sum(phase["duration_seconds"] for phase in phases),
        "phases": phases,
    }
    if details:
        result["details"] = details
    failure_categories = [
        phase.get("failure_category")
        for phase in phases
        if phase.get("failure_category")
    ]
    if failure_categories:
        result["failure_category"] = failure_categories[0]
    return result


def pytest_sessionstart(session: pytest.Session) -> None:
    global _REPORT_CONFIG

    config = session.config
    _REPORT_CONFIG = config
    config._copilot_report_started_at = _utc_now()
    config._copilot_report_started_perf = time.perf_counter()
    config._copilot_report_results = {}
    config._copilot_report_collection_errors = []
    config._copilot_report_internal_errors = []


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when in {"setup", "call", "teardown"}:
        results = getattr(_REPORT_CONFIG, "_copilot_report_results", None)
        if results is not None:
            phases = results.setdefault(report.nodeid, [])
            phases.append(_phase_record(report))
    if report.when == "call" and _is_provider_test(report.nodeid):
        print(
            f"[progress] END {report.nodeid} outcome={report.outcome}",
            flush=True,
        )


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if report.failed:
        collection_errors = getattr(_REPORT_CONFIG, "_copilot_report_collection_errors", None)
        if collection_errors is not None:
            collection_errors.append({
                "nodeid": report.nodeid,
                "details": _safe_text(report.longrepr),
            })


def pytest_internalerror(excrepr: Any, excinfo: Any) -> None:
    internal_errors = getattr(_REPORT_CONFIG, "_copilot_report_internal_errors", None)
    if internal_errors is not None:
        internal_errors.append(_safe_text(excrepr))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    path = _report_path(config)
    if path is None:
        return

    results = [
        _build_test_result(nodeid, phases)
        for nodeid, phases in getattr(config, "_copilot_report_results", {}).items()
    ]
    counts = {
        outcome: sum(result["outcome"] == outcome for result in results)
        for outcome in ("passed", "failed", "skipped", "xfailed", "xpassed")
    }
    failure_categories: dict[str, int] = {}
    for result in results:
        category = result.get("failure_category")
        if category:
            failure_categories[category] = failure_categories.get(category, 0) + 1
    end_perf = time.perf_counter()
    report_data = {
        "schema_version": "1.0",
        "run": {
            "started_at": getattr(config, "_copilot_report_started_at", None),
            "finished_at": _utc_now(),
            "duration_seconds": end_perf - getattr(
                config, "_copilot_report_started_perf", end_perf
            ),
            "exit_status": exitstatus,
            "command": sys.argv,
            "cwd": str(Path.cwd()),
            "python_version": sys.version,
            "pytest_version": pytest.__version__,
            "platform": platform.platform(),
            "git_commit": _git_commit(),
            "configuration": {
                name: os.environ.get(name)
                for name in (
                    "RUN_LLM_EVALS",
                    "COPILOT_BACKEND",
                    "COPILOT_MODEL",
                    "COPILOT_JUDGE_MODEL",
                )
                if os.environ.get(name) is not None
            },
        },
        "summary": {
            **counts,
            "errors": len(getattr(config, "_copilot_report_collection_errors", []))
            + len(getattr(config, "_copilot_report_internal_errors", [])),
            "total": len(results),
            "duration_seconds": sum(result["duration_seconds"] for result in results),
            "failure_categories": failure_categories,
        },
        "tests": results,
        "collection_errors": getattr(config, "_copilot_report_collection_errors", []),
        "internal_errors": getattr(config, "_copilot_report_internal_errors", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary_file:
        json.dump(report_data, temporary_file, indent=2)
        temporary_path = Path(temporary_file.name)
    os.replace(temporary_path, path)
    print(f"[report] JSON results written to {path}", flush=True)


def _is_provider_test(nodeid: str) -> bool:
    return (
        "test_scenarios_live.py::" in nodeid
        or "test_redteam.py::TestRedTeamScenarios::test_scenario_resists_attack" in nodeid
        or "test_redteam.py::TestRedTeamScenarios::test_redteam_suite_options" in nodeid
    )


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int, str]) -> None:
    if _is_provider_test(nodeid):
        print(f"[progress] START {nodeid}", flush=True)


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
