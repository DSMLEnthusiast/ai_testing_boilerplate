# MCP Tool-Calling Evaluation Boilerplate

Single-track deterministic MCP tool-calling testbed with optional DeepEval, MEAI, and GitHub Copilot SDK integrations.

## Layout

- `src/mcp_app`: the single MCP application, implemented with the Python `mcp` package, plus schemas and operations.
- `evals/eval_python/test_agent`: deterministic scenario tests (no API required, always runs).
- `evals/eval_python`: agent evaluation framework with Copilot SDK and DeepEval integration.
- `evals/meaieval`: .NET `Microsoft.Extensions.AI` evaluation example.
- `evals/golden`: shared scenarios and expected results.

## Deterministic checks (no API required)

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
# Run deterministic scenario tests
pytest evals/eval_python/test_agent/test_scenarios_deterministic.py -v

# Or run model-free scenario runner
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
python -m pip install -r requirements.txt
```

The Copilot SDK backend is intentionally opt-in. Set `RUN_LLM_EVALS=1` before
running provider-backed tests. The system under test uses `CopilotBackend`,
while DeepEval metrics use an independent `CopilotLLM` judge. Configure them
separately with `COPILOT_MODEL` and `COPILOT_JUDGE_MODEL`:

```powershell
$env:RUN_LLM_EVALS = "1"
$env:COPILOT_MODEL = "gpt-5"
$env:COPILOT_JUDGE_MODEL = "gpt-4o"
python -m pytest evals/deepeval/correctness/test_correctness.py -v
```

Deterministic tool names, arguments, results, and error categories remain
authoritative over judge output. Judge or provider failures are recorded as
evaluation failures and are not counted as agent vulnerabilities.

## Testing Layers

This framework provides three distinct testing layers:

1. **Deterministic Layer** (`evals/eval_python/test_agent/test_scenarios_deterministic.py` - always runs, no API calls): Validates scenario schema, verifies expected results, and executes scenarios locally using `operations.execute()`. Tests tool invocation, error handling, and response correctness without needing any LLM backend. This is your CI/CD gate.

2. **Integration Layer** (`evals/eval_python/test_agent/test_scenarios_integration.py` - opt-in): Runs scenarios through framework-specific integrations (DeepEval, MEAI) with synthetic or local model results.

3. **Live Layer** (`evals/eval_python/test_agent/test_scenarios_live.py` - opt-in, real LLM calls): Runs the same scenarios through the actual Copilot SDK backend to see how well real AI models handle tool calling. Includes autonomous evaluation via DeepEval metrics that judge whether the agent's response was appropriate.

4. **Red-Team Layer** (security testing): Adversarial attacks to find model vulnerabilities—prompt injection, jailbreaks, PII leakage, etc. Uses DeepTeam for dynamic vulnerability generation.

## Detailed Architecture

### Core Components
- **`src/mcp_app/`**: MCP server with schemas, operations, and tool definitions
- **`evals/eval_python/test_agent/`**: Deterministic scenario tests (no API, CI/CD gate)
  - `test_scenarios_deterministic.py`: Validates scenarios and executes them locally
  - `test_scenarios_integration.py`: Framework integration tests with synthetic results
  - `test_scenarios_live.py`: Live evaluation with real LLM (opt-in)
- **`evals/eval_python/`**: Agent evaluation framework
  - `copilot_backend.py`: Contains `BaseLLM` (abstract), `CopilotLLM` (Copilot SDK implementation)
  - `copilot_llm.py`: Contains `CopilotLLMJudge` (DeepEval judge)
  - `trace.py`: Tool trace normalization
- **`evals/golden/`**: Test scenarios and expected results (scenarios.json, expected-results.json)

### Class Hierarchy
```python
BaseLLM (abstract)
├── CopilotLLM (Copilot SDK agent executor)

CopilotLLMJudge (DeepEval judge for metric evaluation)
```

### Backend Usage
```python
from evals.eval_python import BaseLLM, CopilotLLM

# Agent backend
backend = CopilotLLM()
result = backend.run("user prompt")  # Returns dict with response, tool_calls, etc.

# Judge backend
from evals.eval_python import CopilotLLMJudge
judge = CopilotLLMJudge(model="gpt-4o")
score = judge.generate(prompt, schema=MetricType)
```

### Test Structure
- Use `@pytest.mark.parametrize` with scenario IDs for test discovery
- Filter scenarios by type: `tool_scenarios`, `metric_only_scenarios`, `error_scenarios`, `security_scenarios`
- Conftest provides fixture loading and credential validation

## Development Guidelines

### Naming Conventions
- **Classes**: `BaseLLM`, `CopilotLLM`, `CopilotLLMJudge` (clear, no "Agent" or "Backend" suffixes)
- **Functions**: `run()` (sync), `run_async()` (async), `a_generate()` (async judge)
- **Constants**: UPPERCASE (e.g., DEEPTEAM_VULNERABILITIES)

### Credential Management
- Create `.env` from `.env.example` for local development
- Set `COPILOT_GITHUB_TOKEN` with your GitHub PAT
- Optional: `COPILOT_MODEL` (default: gpt-5), `COPILOT_JUDGE_MODEL` (default: gpt-4o)
- Loaded automatically via `python-dotenv` in conftest

### Code Style
- Type hints required (use `from __future__ import annotations`)
- Docstrings for classes and public methods
- Async patterns: `asyncio.run()`, `asyncio.wait_for()` with timeout
- Error handling: Provide clear messages distinguishing SDK errors, auth errors, execution errors

## Common Tasks

### Add a New Test Scenario
1. Add JSON to `evals/golden/scenarios.json` with: `id`, `prompt`, `expected_tools` or `metric_type`
2. Add expected results to `evals/golden/expected-results.json`
3. Tests auto-parametrize by scenario ID

### Create a Custom Backend
1. Inherit from `BaseLLM`
2. Implement `run(prompt: str) -> dict[str, Any]` with keys: `response`, `tool_calls`, `tool_results`, `usage`, `latency_ms`
3. Update `evals/eval_python/__init__.py` exports

### Extend Red-Team Testing
- Modify `test_redteam/redteam_adapter.py` for attack strategies
- Use `MultiTurnAttackSession` for stateful attacks
- Leverage `DeepTeam` for dynamic vulnerability generation

## Debugging Tips
- Check `.env` exists and `COPILOT_GITHUB_TOKEN` is set for live tests
- Use `-s` flag to see print output: `pytest -s`
- Enable verbose logging with `-vv`
- Inspect scenario fixtures: `print(scenario)` in test
- Check Copilot CLI: `copilot --version`, `copilot auth status`

## References
- [GitHub Copilot SDK Docs](https://github.com/github/copilot-sdk)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [DeepEval](https://docs.confident-ai.com/)
