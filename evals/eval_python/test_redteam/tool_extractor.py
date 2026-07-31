"""Extract tool descriptions and schemas for context-aware red-team attacks.

This module extracts tool metadata from the MCP server to enable redteamers
to generate attacks that are aware of available capabilities and tool signatures.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any


def extract_tools_from_mcp() -> dict[str, dict[str, Any]]:
    """Extract tool descriptions and schemas from the math-mcp server.

    Returns:
        Dict mapping tool names to their metadata:
        {
            "tool_name": {
                "description": "Tool description",
                "parameters": {"param_name": "type", ...},
                "required_parameters": ["param1", ...],
            }
        }
    """
    try:
        # Add src to path for imports
        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root / "src") not in sys.path:
            sys.path.insert(0, str(repo_root / "src"))

        from mcp_app import server

        tools = {}

        # Extract from FastMCP decorated functions
        mcp_instance = server.mcp

        # FastMCP stores tools in _tools attribute
        if hasattr(mcp_instance, "_tools"):
            for tool_name, tool_info in mcp_instance._tools.items():
                tools[tool_name] = {
                    "description": tool_info.get("description", ""),
                    "parameters": extract_function_params(
                        getattr(server, tool_name, None)
                    ),
                    "required_parameters": extract_required_params(
                        getattr(server, tool_name, None)
                    ),
                }
        else:
            # Fallback: extract from module functions
            for name, obj in inspect.getmembers(server, inspect.isfunction):
                if not name.startswith("_"):
                    sig = inspect.signature(obj)
                    tools[name] = {
                        "description": (obj.__doc__ or "").strip(),
                        "parameters": {
                            param_name: str(param.annotation)
                            for param_name, param in sig.parameters.items()
                        },
                        "required_parameters": [
                            param_name
                            for param_name, param in sig.parameters.items()
                            if param.default == inspect.Parameter.empty
                        ],
                    }

        return tools

    except Exception as error:
        raise RuntimeError(f"Failed to extract tools from MCP: {error}") from error


def extract_function_params(func: Any) -> dict[str, str]:
    """Extract parameter names and types from a function."""
    if func is None:
        return {}

    try:
        sig = inspect.signature(func)
        return {
            param_name: str(param.annotation).replace("typing.", "")
            for param_name, param in sig.parameters.items()
        }
    except Exception:
        return {}


def extract_required_params(func: Any) -> list[str]:
    """Extract required (non-default) parameter names from a function."""
    if func is None:
        return []

    try:
        sig = inspect.signature(func)
        return [
            param_name
            for param_name, param in sig.parameters.items()
            if param.default == inspect.Parameter.empty
        ]
    except Exception:
        return []


def format_tools_for_context(tools: dict[str, dict[str, Any]]) -> str:
    """Format extracted tools into a context string for attack generation.

    Args:
        tools: Dictionary of tool metadata

    Returns:
        Formatted string describing available tools
    """
    lines = ["Available tools and their signatures:\n"]

    for tool_name, tool_info in sorted(tools.items()):
        description = tool_info.get("description", "No description")
        params = tool_info.get("parameters", {})
        required = tool_info.get("required_parameters", [])

        param_list = ", ".join(
            f"{name}: {ptype}{'*' if name in required else '?'}"
            for name, ptype in params.items()
        )

        lines.append(f"- {tool_name}({param_list})")
        lines.append(f"  Description: {description}")

    return "\n".join(lines)
