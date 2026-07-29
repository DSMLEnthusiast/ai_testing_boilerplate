"""DeepEval v2: Scenario-based systematic evaluation suite.

Three-layer test architecture:
1. Deterministic: Load fixtures, execute locally, verify results (CI gate)
2. Live: Run through Copilot backend with DeepEval judge (manual testing)
3. Integration: End-to-end pipeline validation

Core utilities:
- copilot_backend: BaseLLM abstract class and CopilotLLM for Copilot SDK execution
- copilot_llm: CopilotLLMJudge for DeepEval judge evaluation
- trace: Tool trace normalization for DeepEval metrics

Note: base.py has been merged into copilot_backend.py
"""

from .copilot_backend import BaseLLM, CopilotLLM
from .copilot_llm import CopilotLLMJudge
from .trace import normalize_tool_trace, to_deepeval_tool_calls

__all__ = [
    'BaseLLM',
    'CopilotLLM',
    'CopilotLLMJudge',
    'normalize_tool_trace',
    'to_deepeval_tool_calls',
]
