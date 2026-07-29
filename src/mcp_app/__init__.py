"""Shared MCP application used by all Python evaluation adapters."""

from .contracts import JudgeVerdict, NormalizedRun
from .operations import OperationError, execute
from .server import mcp, run_stdio

__all__ = [
    "JudgeVerdict",
    "NormalizedRun",
    "OperationError",
    "execute",
    "mcp",
    "run_stdio",
]
