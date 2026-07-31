"""Live scenario tests with Copilot backend and DeepEval judge.

Requires:
    RUN_LLM_EVALS=1 to enable
    Copilot SDK installed (pip install github-copilot-sdk)
    copilot CLI available (bundled with SDK)
    Authentication configured (COPILOT_GITHUB_TOKEN env var or 'copilot auth login')
    COPILOT_BACKEND (optional, mcp or agent; defaults to mcp)
    COPILOT_MODEL (optional, defaults to gpt-5-mini)
    COPILOT_JUDGE_MODEL (optional, defaults to gpt-5-mini)

This suite:
1. Runs scenarios through CopilotLLM with native tracing
2. Evaluates with ToolCorrectnessMetric (for tool-based scenarios)
3. Evaluates with AnswerRelevancyMetric (for all scenarios)
4. Evaluates with TaskCompletionMetric (for all scenarios)
5. Evaluates with StepEfficiencyMetric (for tool-based scenarios)
6. Evaluates with PromptAlignmentMetric (for all scenarios, using the
   scenario's judge rubric as the instruction contract)
7. Uses independent CopilotLLMJudge for each metric
8. Reports DeepEval native scores and pass/fail

Run with:
    RUN_LLM_EVALS=1 pytest evals/eval_python/test_agent/test_scenarios_live.py -v -s
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

pytest.importorskip("deepeval", reason="install the deepeval extra")

from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import (
    AnswerRelevancyMetric,
    PromptAlignmentMetric,
    StepEfficiencyMetric,
    TaskCompletionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import ToolCall
from deepeval.tracing import observe, update_current_trace

from ..conftest import get_live_test_skip_reason
from ..copilot_backend import create_copilot_backend
from ..copilot_llm import CopilotLLMJudge
from ..trace import normalize_tool_trace, require_successful_run, to_deepeval_tool_calls


skip_if_not_live = pytest.mark.skipif(
    get_live_test_skip_reason() is not None,
    reason=get_live_test_skip_reason() or "unknown reason",
)


def _run_live_agent(backend: Any, user_input: str) -> dict[str, Any]:
    return dict(require_successful_run(backend.run(user_input)))


def _require_live_agent_scenario(scenario: dict[str, Any]) -> None:
    """Skip scenarios that target the MCP server contract directly.

    ``target_boundary: "server"`` scenarios (e.g. malformed arguments,
    unknown tools) validate deterministic MCP protocol behavior and are
    covered by test_scenarios_deterministic.py / test_scenarios_integration.py.
    They are not meaningful judged-agent correctness cases here because the
    live agent's natural-language prompt may not even reproduce the
    malformed call the scenario is targeting.
    """
    if scenario.get("target_boundary") == "server":
        pytest.skip(
            "server-boundary scenario; validated via deterministic MCP "
            "contract tests, not live agent judge metrics"
        )


class TestScenariosToolCorrectness:
    """Evaluate tool correctness for each scenario.

    Skips metric-only scenarios (no expected_tools).
    Uses ToolCorrectnessMetric with independent CopilotLLMJudge judge.
    """

    @skip_if_not_live
    def test_scenario_tool_correctness(
        self, scenario: dict[str, Any]
    ) -> None:
        """Evaluate tool correctness for this scenario."""
        _require_live_agent_scenario(scenario)
        if not scenario.get("expected_tools"):
            pytest.skip("metric-only scenario (no expected_tools)")

        # Create Golden test case with expected tool calls
        expected_tool_calls = [
            ToolCall(name=call["name"], arguments=call.get("arguments", {}))
            for call in scenario["expected_tools"]
        ]
        expected_output = json.dumps(scenario.get("expected", {}))

        golden = Golden(
            input=scenario["prompt"],
            expected_output=expected_output,
            expected_tools=expected_tool_calls,
        )

        # Create dataset with this single scenario
        dataset = EvaluationDataset(goldens=[golden])

        # Create backend (fresh instance per test)
        backend = create_copilot_backend()

        # Define agent with tracing
        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            golden = dataset.goldens[0]
            if golden:
                update_current_trace(
                    expected_tools=golden.expected_tools,
                    expected_output=golden.expected_output,
                )

            result = _run_live_agent(backend, user_input)
            actual_calls = normalize_tool_trace(result)
            update_current_trace(
                tools_called=to_deepeval_tool_calls(actual_calls),
                output=result.get("response", ""),
            )
            return str(result.get("response", ""))

        # Evaluate with independent judge
        judge = CopilotLLMJudge()
        metrics = [ToolCorrectnessMetric(model=judge, threshold=0.7)]

        # Run evaluation through dataset iterator
        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)


class TestScenariosAnswerRelevancy:
    """Evaluate answer relevancy for each scenario.

    Runs all scenarios (both tool-based and metric-only).
    Uses AnswerRelevancyMetric with independent CopilotLLMJudge judge.
    """

    @skip_if_not_live
    def test_scenario_answer_relevancy(
        self, scenario: dict[str, Any]
    ) -> None:
        """Evaluate answer relevancy for this scenario."""
        _require_live_agent_scenario(scenario)

        # Create Golden test case. Fall back through the available fixture
        # fields: a full expected response, a substring the response must
        # contain (e.g. refusal scenarios), then the structured expected
        # result.
        expected_output = (
            scenario.get("expected_response")
            or scenario.get("expected_response_contains")
            or json.dumps(scenario.get("expected", {}))
        )
        golden = Golden(
            input=scenario["prompt"],
            expected_output=expected_output,
        )

        # Create dataset with this single scenario
        dataset = EvaluationDataset(goldens=[golden])

        # Create backend (fresh instance per test)
        backend = create_copilot_backend()

        # Define agent with tracing
        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            result = _run_live_agent(backend, user_input)
            update_current_trace(output=result.get("response", ""))
            return str(result.get("response", ""))

        # Evaluate with independent judge
        judge = CopilotLLMJudge()
        metrics = [AnswerRelevancyMetric(model=judge, threshold=0.7)]

        # Run evaluation through dataset iterator
        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)


class TestScenariosTaskCompletion:
    """Evaluate whether the agent actually completed the requested task.

    Runs all scenarios (both tool-based and metric-only). Unlike
    ToolCorrectness/AnswerRelevancy, TaskCompletionMetric reads the tool
    trace attached to the current span by the tracer, so the test only
    needs to set input/output on the trace.
    """

    @skip_if_not_live
    def test_scenario_task_completion(self, scenario: dict[str, Any]) -> None:
        """Evaluate task completion for this scenario."""
        _require_live_agent_scenario(scenario)
        golden = Golden(input=scenario["prompt"])
        dataset = EvaluationDataset(goldens=[golden])

        backend = create_copilot_backend()

        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            result = _run_live_agent(backend, user_input)
            actual_calls = normalize_tool_trace(result)
            update_current_trace(
                tools_called=to_deepeval_tool_calls(actual_calls),
                output=result.get("response", ""),
            )
            return str(result.get("response", ""))

        judge = CopilotLLMJudge()
        metrics = [
            TaskCompletionMetric(
                model=judge,
                threshold=0.7,
                task=(
                    "Use the math MCP tools to compute the correct result "
                    "for the user's request, or clearly refuse if the "
                    "operation is unsupported."
                ),
            )
        ]

        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)


class TestScenariosStepEfficiency:
    """Evaluate whether the agent used tool calls efficiently.

    Skips metric-only scenarios (no expected_tools) because step
    efficiency is only meaningful when tool calls are expected.
    """

    @skip_if_not_live
    def test_scenario_step_efficiency(self, scenario: dict[str, Any]) -> None:
        """Evaluate step efficiency for this scenario."""
        _require_live_agent_scenario(scenario)
        if not scenario.get("expected_tools"):
            pytest.skip("metric-only scenario (no expected_tools)")

        golden = Golden(input=scenario["prompt"])
        dataset = EvaluationDataset(goldens=[golden])

        backend = create_copilot_backend()

        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            result = _run_live_agent(backend, user_input)
            actual_calls = normalize_tool_trace(result)
            update_current_trace(
                tools_called=to_deepeval_tool_calls(actual_calls),
                output=result.get("response", ""),
            )
            return str(result.get("response", ""))

        judge = CopilotLLMJudge()
        metrics = [StepEfficiencyMetric(model=judge, threshold=0.7)]

        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)


class TestScenariosPromptAlignment:
    """Evaluate whether responses honor the scenario's judge-rubric contract.

    Runs all scenarios. The rubric criteria for the scenario's rubric_id
    (see evals/golden/judge-rubrics.json) are used as the
    PromptAlignmentMetric instruction set, since this agent has no
    separate system-prompt fixture to draw instructions from.
    """

    @skip_if_not_live
    def test_scenario_prompt_alignment(
        self, scenario: dict[str, Any], judge_rubrics: dict[str, Any]
    ) -> None:
        """Evaluate prompt alignment for this scenario."""
        _require_live_agent_scenario(scenario)
        rubric_id = scenario.get("rubric_id")
        rubric = judge_rubrics.get(rubric_id, {}) if rubric_id else {}
        prompt_instructions = rubric.get("criteria")
        if not prompt_instructions:
            pytest.skip(f"no judge rubric instructions found for rubric_id={rubric_id!r}")

        golden = Golden(input=scenario["prompt"])
        dataset = EvaluationDataset(goldens=[golden])

        backend = create_copilot_backend()

        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            result = _run_live_agent(backend, user_input)
            update_current_trace(output=result.get("response", ""))
            return str(result.get("response", ""))

        judge = CopilotLLMJudge()
        metrics = [
            PromptAlignmentMetric(
                prompt_instructions=prompt_instructions,
                model=judge,
                threshold=0.7,
            )
        ]

        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)
