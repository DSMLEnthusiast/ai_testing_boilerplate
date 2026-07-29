from __future__ import annotations

from typing import Any

from .operations import OperationError, execute

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("math-mcp")

@mcp.tool(description="Add two finite unitless numbers a and b. Returns a structured value and operation.")
def add(a: float, b: float) -> dict[str, Any]:
    return execute("add", {"a": a, "b": b})

@mcp.tool(description="Subtract finite unitless number b from a. Returns a structured value and operation.")
def subtract(a: float, b: float) -> dict[str, Any]:
    return execute("subtract", {"a": a, "b": b})

@mcp.tool(description="Multiply two finite unitless numbers a and b. Returns a structured value and operation.")
def multiply(a: float, b: float) -> dict[str, Any]:
    return execute("multiply", {"a": a, "b": b})

@mcp.tool(description="Divide finite unitless number a by b; b must not be zero.")
def divide(a: float, b: float) -> dict[str, Any]:
    return execute("divide", {"a": a, "b": b})

@mcp.tool(description="Raise finite unitless base to finite exponent; unsupported real-valued domains fail.")
def power(base: float, exponent: float) -> dict[str, Any]:
    return execute("power", {"base": base, "exponent": exponent})

@mcp.tool(description="Compute e raised to finite unitless x; overflow is reported as non_finite_result.")
def exp(x: float) -> dict[str, Any]:
    return execute("exp", {"x": x})

@mcp.tool(description="Compute the natural log of positive unitless x, or log base positive base (not 1).")
def log(x: float, base: float | None = None) -> dict[str, Any]:
    arguments: dict[str, Any] = {"x": x}
    if base is not None:
        arguments["base"] = base
    return execute("log", arguments)


def run_stdio() -> None:
    """Run the official MCP stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
