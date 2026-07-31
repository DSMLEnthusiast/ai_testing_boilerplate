"""Shared Python and .NET evaluation entry points.

Deterministic and provider-backed Python evaluations live in
``evals/eval_python``. The .NET Copilot SDK example lives in
``evals/eval_dotnet``, and both use fixtures from ``evals/golden``.
"""

from pathlib import Path

try:
  from dotenv import load_dotenv
except ImportError:
  pass
else:
  load_dotenv(Path(__file__).resolve().parents[1] / ".env")

