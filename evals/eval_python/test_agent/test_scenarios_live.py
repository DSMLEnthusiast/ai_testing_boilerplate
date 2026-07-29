"""Live scenario tests with Copilot backend and DeepEval judge.

Requires:
    RUN_LLM_EVALS=1 to enable
    Copilot SDK installed (pip install github-copilot-sdk)
    copilot CLI available (bundled with SDK)
    Authentication configured (COPILOT_GITHUB_TOKEN env var or 'copilot auth login')
    COPILOT_MODEL (optional, defaults to gpt-5)
    COPILOT_JUDGE_MODEL (optional, defaults to gpt-4o)

This suite:
1. Runs scenarios through CopilotLLM with native tracing
2. Evaluates with ToolCorrectnessMetric (for tool-based scenarios)
3. Evaluates with AnswerRelevancyMetric (for all scenarios)
4. Uses independent CopilotLLMJudge for each metric
5. Reports DeepEval native scores and pass/fail

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
from deepeval.metrics import AnswerRelevancyMetric, ToolCorrectnessMetric
from deepeval.test_case import ToolCall
from deepeval.tracing import observe, update_current_trace

from .conftest import get_live_test_skip_reason
from ..copilot_backend import CopilotLLM
from ..copilot_llm import CopilotLLMJudge
from ..trace import normalize_tool_trace, to_deepeval_tool_calls


skip_if_not_live = pytest.mark.skipif(
    get_live_test_skip_reason() is not None,
    reason=get_live_test_skip_reason() or "unknown reason",
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
        backend = CopilotLLM()

        # Define agent with tracing
        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            golden = dataset.goldens[0]
            if golden:
                update_current_trace(
                    expected_tools=golden.expected_tools,
                    expected_output=golden.expected_output,
                )

            result = backend.run(user_input)
            actual_calls = normalize_tool_trace(result)
            update_current_trace(
                tools=to_deepeval_tool_calls(actual_calls),
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
        # Create Golden test case
        golden = Golden(
            input=scenario["prompt"],
            expected_output=scenario.get(
                "expected_response", json.dumps(scenario.get("expected", {}))
            ),
        )

        # Create dataset with this single scenario
        dataset = EvaluationDataset(goldens=[golden])

        # Create backend (fresh instance per test)
        backend = CopilotLLM()

        # Define agent with tracing
        @observe(name="math_agent")
        def math_agent(user_input: str) -> str:
            result = backend.run(user_input)
            update_current_trace(output=result.get("response", ""))
            return str(result.get("response", ""))

        # Evaluate with independent judge
        judge = CopilotLLMJudge()
        metrics = [AnswerRelevancyMetric(model=judge, threshold=0.7)]

        # Run evaluation through dataset iterator
        for golden in dataset.evals_iterator(metrics=metrics):
            math_agent(golden.input)
