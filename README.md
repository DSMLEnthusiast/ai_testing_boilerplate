# MCP Tool-Calling Evaluation Boilerplate

Single-track deterministic MCP tool-calling testbed with optional DeepEval, MEAI, and GitHub Copilot SDK integrations.

## Layout

- `src/mcp_app`: the single MCP application, implemented with the Python `mcp` package, plus schemas and operations.
- `evals`: normalized contracts, model-free scenario runner, and evaluation adapters.
- `tests`: deterministic unit, protocol, and fixture tests.
- `evals/deepeval`: Python DeepEval adapter and Copilot SDK helper.
- `evals/meaieval`: .NET `Microsoft.Extensions.AI` evaluation example.
- `fixtures`: shared scenarios and expected results.

## Deterministic checks

```powershell
python -m pip install -e ".[test]"
$env:PYTHONPATH = "src"
pytest -q
python evals/run_scenarios.py --repetitions 2 --output results.json
```

No API key or network access is required. The server is available over stdio:

```powershell
$env:PYTHONPATH = "src"
python -m mcp_app.server
```

## Optional LLM evaluation

Install the desired optional dependencies:

```powershell
python -m pip install -e ".[deepeval,copilot]"
```

The Copilot SDK backend is intentionally opt-in. Configure the system-under-test and judge independently, then use the helper in the relevant `evals/<framework>/` directory. Deterministic tool names, arguments, results, and error categories remain authoritative over judge output.
