"""Framework-specific evaluation entry points.

The evaluation infrastructure has been reorganized:

Shared/Core infrastructure:
  - src/mcp_app/contracts.py          → Normalized run and judge verdict schemas
  - tests/model_free/scenario_runner.py → Deterministic scenario execution
  - tests/model_free/run.py           → Model-free CLI runner

Framework adapters:
  - evals/deepeval/                   → DeepEval evaluation adapter (Python)
  - evals/meaieval/                   → MEAI/Copilot SDK adapter (.NET)
  - evals/agenteval/                  → AgentEval adapter (if supported)

Legacy files in evals/ have been moved to their proper locations above.
See docs/plan.md for the full architecture.
"""

from pathlib import Path

try:
  from dotenv import load_dotenv
except ImportError:
  pass
else:
  load_dotenv(Path(__file__).resolve().parents[1] / ".env")

