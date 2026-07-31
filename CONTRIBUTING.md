# Contributing to MCP Tool-Calling Evaluation Boilerplate

Thank you for your interest in contributing! This guide explains how to extend the repository with new tools, scenarios, and evaluation adapters while maintaining the shared contract.

## Core Principles

- **Single shared implementation**: All Python evaluation adapters use `src/mcp_app/`
- **Deterministic by default**: Changes must preserve offline, API-key-free testing
- **Normalized results**: Every evaluation produces the same result schema
- **Schema synchronization**: Tool changes require synchronized updates across evals/golden, tests, and adapters

## Adding a New Math Operation

### 1. Implement the operation

Edit [src/mcp_app/operations.py](src/mcp_app/operations.py):

```python
# Add the operation name to _SCHEMAS
_SCHEMAS = {
    "add": frozenset({"a", "b"}),
    # ... existing operations ...
    "my_operation": frozenset({"arg1", "arg2"}),  # Define required arguments
}

# In execute(), add your operation logic
elif operation == "my_operation":
    value = my_logic(values["arg1"], values["arg2"])
```

Handle errors using the standard error categories:
- `invalid_arguments`: Schema/type/range validation
- `division_by_zero`: Specific to divide operation
- `domain_error`: Math domain constraints (e.g., log of negative)
- `non_finite_result`: Overflow or infinite result

### 2. Register the MCP tool

Edit [src/mcp_app/server.py](src/mcp_app/server.py):

```python
@mcp.tool(description="Clear, complete description of what the operation does and constraints.")
def my_operation(arg1: float, arg2: float) -> dict[str, Any]:
    return execute("my_operation", {"arg1": arg1, "arg2": arg2})
```

### 3. Add unit tests

Add focused cases to [evals/eval_python/test_agent/test_scenarios_deterministic.py](evals/eval_python/test_agent/test_scenarios_deterministic.py):

```python
@pytest.mark.parametrize(
    ("operation", "arguments", "expected"),
    [("my_operation", {"arg1": 2, "arg2": 3}, 5)],  # Normal case
)
def test_my_operation(operation, arguments, expected):
    assert execute(operation, arguments)["value"] == expected

@pytest.mark.parametrize(
    ("operation", "arguments", "category"),
    [("my_operation", {"arg1": "invalid"}, "invalid_arguments")],  # Error case
)
def test_my_operation_errors(operation, arguments, category):
    with pytest.raises(OperationError) as error:
        execute(operation, arguments)
    assert error.value.category == category
```

### 4. Add test scenarios

Edit [evals/golden/scenarios.json](evals/golden/scenarios.json):

```json
{
  "id": "my-operation-basic",
  "prompt": "What is my_operation(2, 3)?",
  "target_boundary": "end-to-end",
  "rubric_id": "math-tool-v1",
  "expected_tools": [{"name": "my_operation", "arguments": {"arg1": 2, "arg2": 3}}],
  "expected": {"value": 5, "operation": "my_operation"}
}
```

### 5. Run tests

```bash
# Deterministic fixture and operation tests
python -m pytest evals/eval_python/test_agent/test_scenarios_deterministic.py -v

# Verify all offline tests pass
python -m pytest -m "not live"
```

## Adding a New Evaluation Scenario

### 1. Create the scenario in evals/golden/scenarios.json

```json
{
  "id": "unique-scenario-id",
  "prompt": "User-facing prompt here",
  "target_boundary": "end-to-end|agent|server",
  "rubric_id": "math-tool-v1",
  "expected_tools": [
    {"name": "tool_name", "arguments": {"arg": "value"}}
  ],
  "expected": {"value": 5, "operation": "tool_name"}
}
```

- `id`: Unique identifier for the scenario
- `prompt`: What the LLM should read
- `target_boundary`:
  - `end-to-end`: Full agent + server integration
  - `agent`: Agent planning (no server execution)
  - `server`: Server protocol validation
- `expected_tools`: Tool calls that should occur
- `expected`: Numeric result OR `expected_error` for error cases

### 2. Test deterministically

```bash
python -m pytest evals/eval_python/test_agent/test_scenarios_deterministic.py -v
```

## Creating a New Evaluation Adapter

### 1. Create adapter directory

```bash
mkdir -p evals/my_framework
touch evals/my_framework/__init__.py
touch evals/my_framework/adapter.py
touch evals/my_framework/test_adapter.py
touch evals/my_framework/run.py
```

### 2. Implement the adapter

File: `evals/my_framework/adapter.py`

```python
from typing import Any

def run_my_framework_test(scenario: dict[str, Any], backend: Any, **options) -> dict[str, Any]:
    """Run one scenario through the framework.

    Returns normalized result with:
    - run_id, scenario_id, framework, agent_runtime, model_provider
    - repetition_index, passed, native_score, reason, latency_ms
    """
    # Your framework-specific evaluation logic
    return {
        "run_id": f"my-framework-{scenario['id']}-{uuid.uuid4().hex[:8]}",
        "scenario_id": scenario["id"],
        "framework": "MyFramework",
        "agent_runtime": "your-backend",
        "model_provider": "your-model",
        "repetition_index": 0,
        "passed": True,
        "native_score": 1.0,
        "reason": "evaluation reason",
        "latency_ms": 100.5,
    }
```

### 3. Write adapter tests

File: `evals/my_framework/test_adapter.py`

```python
from unittest.mock import MagicMock
from evals.my_framework.adapter import run_my_framework_test

def test_adapter_normalizes_to_shared_schema():
    scenario = {
        "id": "test",
        "prompt": "Test",
        "expected_tools": []
    }
    backend = MagicMock()
    backend.run.return_value = {"response": "test"}

    result = run_my_framework_test(scenario, backend)

    # Verify normalized schema
    assert result["run_id"]
    assert result["scenario_id"] == "test"
    assert result["framework"] == "MyFramework"
    assert "passed" in result
    assert "native_score" in result
```

### 4. Create a runner script

File: `evals/my_framework/run.py`

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from evals.my_framework.adapter import run_my_framework_test

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, default=Path("evals/golden/scenarios.json"))
    parser.add_argument("--output", type=Path, default=Path("results-my-framework.json"))
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    scenarios = json.loads(args.scenarios.read_text())
    results = []

    for scenario in scenarios:
        for rep in range(args.repetitions):
            backend = YourBackendClass()  # Your backend initialization
            result = run_my_framework_test(scenario, backend)
            results.append(result)

    args.output.write_text(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
```

### 5. Add optional dependency

Edit [pyproject.toml](pyproject.toml):

```toml
[project.optional-dependencies]
my_framework = ["my-framework-package>=1.0"]
```

Install with:

```bash
pip install -e ".[my_framework]"
```

## Testing Your Changes

### Deterministic checks (no API key required)

```bash
# Install the package and offline test dependencies
python -m pip install -e ".[dev]"

# Run deterministic tests without external providers
python -m pytest -m "not live"
```

### Optional: Live evaluation

```bash
# For DeepEval and Copilot SDK
export RUN_LLM_EVALS=1
python -m pytest evals/eval_python/test_agent/test_scenarios_live.py -v -s

# For your adapter
python evals/my_framework/run.py --repetitions 2
```

## Pull Request Checklist

- [ ] New operation: unit test, MCP test, scenario, expected result added
- [ ] New scenario: evals/golden/scenarios.json updated with its expected outcome
- [ ] New adapter: adapter.py, test_adapter.py, run.py, pyproject.toml updated
- [ ] All deterministic tests pass: `python -m pytest -m "not live"`
- [ ] Normalized result schema validated
- [ ] Error categories used correctly (invalid_arguments, division_by_zero, domain_error, non_finite_result)
- [ ] Documentation updated (docstrings, README if needed)

## Troubleshooting

### "Module not found" errors

Ensure PYTHONPATH includes src:

```bash
export PYTHONPATH=src
python evals/my_framework/run.py
```

### Deterministic tests fail

Check that:
1. Operation validation is correct in `_number()` and `execute()`
2. Error categories match expected values in scenarios.json
3. Numeric tolerances (1e-9) are applied in tests, not in operations

### Adapter test failures

Verify that:
1. Normalized result has all required keys
2. Scenario ID matches input
3. Framework name is consistent
4. Latency and score are numeric

## Questions?

- Review existing operations in [src/mcp_app/operations.py](src/mcp_app/operations.py)
- See scenario examples in [evals/golden/scenarios.json](evals/golden/scenarios.json)
- Check the Python backend reference: [evals/eval_python/copilot_backend.py](evals/eval_python/copilot_backend.py)
