# MEAI Evaluation Adapter

This folder contains a Microsoft.Extensions.AI (MEAI) adapter for running LLM-backed evaluations of the math MCP tool-calling scenarios using the GitHub Copilot SDK.

## Overview

The MEAI adapter demonstrates:
- Real Copilot SDK integration with MCP tool discovery and invocation
- Scenario loading and repeated-run evaluation
- Normalized result output compatible with the shared evaluation contract
- Graceful error handling and provider failure reporting

## Architecture

### CopilotSdkAgent.cs
Wraps the GitHub Copilot SDK client with MCP server configuration:
- Automatically locates the Python MCP server using `pyproject.toml` as a marker
- Configures MCP tool discovery for the shared `math-mcp` server
- Captures latency, response text, and pass/fail status
- Handles session lifecycle and error propagation

### Program.cs
Full evaluation harness:
- Loads scenarios from `evals/golden/scenarios.json`
- Runs each scenario against the Copilot SDK backend
- Supports repeated runs via `--repetitions` parameter
- Normalizes results to the shared contract schema
- Outputs JSON results to a configurable file

### MeaiEvaluator.cs (Optional)
Generic wrapper for any `IChatClient` implementation:
- Useful for evaluating with non-Copilot providers
- Supports environment-configured model selection
- Returns structured results with latency and response text

## Requirements

- .NET 8.0 or later
- `Microsoft.Extensions.AI` (≥10.4.0)
- `GitHub.Copilot.SDK` (≥1.0.0-beta.8)
- Python 3.10+ with the MCP server installed (`pip install -e ".[test]"` in the repo root)

## Setup

### 1. Install .NET dependencies

```bash
dotnet restore
```

### 2. Configure environment

Set the Copilot model and Python executable (optional):

```bash
# Windows PowerShell
$env:COPILOT_MODEL = "gpt-4.1"  # or your chosen model
$env:PYTHON = "python"           # or path to Python executable

# Linux/macOS bash
export COPILOT_MODEL="gpt-4.1"
export PYTHON="python3"
```

### 3. Build

```bash
dotnet build
```

## Usage

### Run scenarios with Copilot SDK

```bash
# Single run
dotnet run

# Multiple repetitions with custom output
dotnet run -- --repetitions 3 --output eval_results.json

# Custom provider setting
dotnet run -- --repetitions 2 --provider copilot-sdk --output results.json
```

### Output format

Results are saved as JSON with one object per scenario/repetition:

```json
[
  {
    "run_id": "meai-add-basic-0",
    "scenario_id": "add-basic",
    "model_provider": "github-copilot-sdk",
    "response": "2 plus 3 equals 5",
    "repetition_index": 0,
    "passed": true,
    "failure_category": "none",
    "latency_ms": 1234.56,
    "target_boundary": "end-to-end",
    "rubric_id": "math-tool-v1"
  }
]
```

## Failure categories

The evaluation uses these standardized categories:
- `none` — Pass or expected behavior
- `provider_error` — Copilot SDK error or network failure
- `malformed_response` — Response did not match expected format
- `tool_invocation_failed` — MCP tool error (e.g., `division_by_zero`, `domain_error`)
- `unsupported_operation` — Agent correctly declined an unsupported request

## Limitations

- Pass/fail determination is currently based on substring matching (`ExpectedResponseContains` from scenarios)
- Tool call tracing and detailed MCP event logs are not yet extracted from the Copilot SDK
- Model comparison and statistical inference are deferred to the [future_statistical_tests_model_comparison_plan.md](../../docs/future_statistical_tests_model_comparison_plan.md)

## Integration with shared contract

This adapter uses:
- Shared scenarios and expected outcomes from `evals/golden/scenarios.json`
- Shared MCP server from `src/mcp_app/`
- Normalized result schema matching the deterministic Python runner

Results can be compared with:
- Model-free deterministic evaluations via `python evals/run_scenarios.py`
- DeepEval results from `evals/deepeval/`

## Development

### Adding new evaluation metrics

Extend the `EvaluationResult` record to capture additional fields, then update `NormalizeResult()` to map them to the output schema.

### Integrating a different LLM provider

Replace the `CopilotSdkAgent` with a similar wrapper around your chosen provider's client, maintaining the same `RunAsync` signature and result schema.

### Testing locally without live API

For deterministic CI testing, provide a synthetic `IChatClient` that returns fixed responses for known scenarios instead of calling Copilot SDK.
