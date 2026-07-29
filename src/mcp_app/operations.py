from __future__ import annotations

import math
from typing import Any


class OperationError(ValueError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


_SCHEMAS = {
    "add": frozenset({"a", "b"}),
    "subtract": frozenset({"a", "b"}),
    "multiply": frozenset({"a", "b"}),
    "divide": frozenset({"a", "b"}),
    "power": frozenset({"base", "exponent"}),
    "exp": frozenset({"x"}),
    "log": frozenset({"x", "base"}),
}
_SIGNED_INTEGER_MAX = 2**63 - 1


def _number(arguments: dict[str, Any], name: str) -> float:
    raw = arguments.get(name)
    if name not in arguments or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise OperationError("invalid_arguments", f"missing or non-numeric argument: {name}")
    value = float(raw)
    if not math.isfinite(value):
        raise OperationError("invalid_arguments", f"argument must be finite: {name}")
    return value


def execute(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if operation not in _SCHEMAS:
        raise OperationError("invalid_arguments", f"unknown operation: {operation}")
    allowed = _SCHEMAS[operation]
    if set(arguments) - allowed:
        raise OperationError("invalid_arguments", "unexpected argument")
    required = {"x"} if operation in {"exp", "log"} else allowed
    if not required.issubset(arguments):
        raise OperationError("invalid_arguments", "missing required argument")

    values = {name: _number(arguments, name) for name in arguments}
    try:
        if operation in {"add", "subtract", "multiply"} and all(
            isinstance(arguments[name], int) and not isinstance(arguments[name], bool)
            for name in ("a", "b")
        ):
            integer_result = {
                "add": arguments["a"] + arguments["b"],
                "subtract": arguments["a"] - arguments["b"],
                "multiply": arguments["a"] * arguments["b"],
            }[operation]
            if abs(integer_result) > _SIGNED_INTEGER_MAX:
                raise OperationError(
                    "non_finite_result",
                    f"{operation} produced a non-finite result",
                )
        if operation == "add":
            value = values["a"] + values["b"]
        elif operation == "subtract":
            value = values["a"] - values["b"]
        elif operation == "multiply":
            value = values["a"] * values["b"]
        elif operation == "divide":
            if values["b"] == 0:
                raise OperationError("division_by_zero", "cannot divide by zero")
            value = values["a"] / values["b"]
        elif operation == "power":
            if values["base"] < 0 and not values["exponent"].is_integer():
                raise OperationError("domain_error", "power has no real-valued result")
            value = math.pow(values["base"], values["exponent"])
        elif operation == "exp":
            value = math.exp(values["x"])
        else:
            base = values.get("base")
            if values["x"] <= 0 or (base is not None and (base <= 0 or base == 1)):
                raise OperationError("domain_error", "invalid logarithm domain or base")
            value = math.log(values["x"], base) if base is not None else math.log(values["x"])
    except OperationError:
        raise
    except OverflowError:
        raise OperationError("non_finite_result", f"{operation} produced a non-finite result") from None
    except ValueError:
        raise OperationError("domain_error", f"invalid domain for {operation}") from None

    if not math.isfinite(value):
        raise OperationError("non_finite_result", f"{operation} produced a non-finite result")
    return {"value": value, "operation": operation}
