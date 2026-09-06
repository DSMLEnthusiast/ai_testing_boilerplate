# MCP Tool-Calling Evaluation Boilerplate

Single-track deterministic MCP tool-calling testbed with optional DeepEval, MEAI, and GitHub Copilot SDK integrations.

## Layout

- `src/mcp_app`: the single MCP application, implemented with the Python `mcp` package, plus schemas and operations.
- `evals/eval_python/test_agent`: deterministic scenario tests (no API required, always runs).
- `evals/eval_python`: agent evaluation framework with Copilot SDK and DeepEval integration.
- `evals/eval_dotnet`: .NET `Microsoft.Extensions.AI` evaluation example.
- `evals/golden`: shared scenarios and expected results.

## Deterministic checks (no API required)

```powershell
python -m pip install -e ".[dev]"
# Run deterministic scenario tests
python -m pytest evals/eval_python/test_agent/test_scenarios_deterministic.py -v
```

No API key or network access is required. The server is available over stdio:

```powershell
$env:PYTHONPATH = "src"
python -m mcp_app.server
```

## Test Commands

Activate the repository virtual environment before running the commands:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies needed for the test layers you plan to run:

```powershell
python -m pip install -e ".[dev]"                 # deterministic, integration, and contract tests
python -m pip install -e ".[dev,live]"            # add live agent and DeepEval tests
python -m pip install -e ".[dev,live,redteam]"   # add red-team generation
```

Run the Python test layers independently:

```powershell
# All offline Python tests; never imports the live scenario module or calls an external LLM
python -m pytest -p no:deepeval `
  evals/eval_python/test_agent/test_scenarios_deterministic.py `
  evals/eval_python/test_agent/test_scenarios_integration.py `
  evals/eval_python/test_agent/test_copilot_backend.py `
  evals/eval_python/test_agent/test_result_contract.py `
  evals/eval_python/test_redteam/test_redteam.py `
  -m "not live" -v

# Add a durable JSON report for post-run review
python -m pytest -p no:deepeval `
  evals/eval_python/test_agent/test_scenarios_deterministic.py `
  evals/eval_python/test_agent/test_scenarios_integration.py `
  -m "not live" -v `
  --test-results-json test-results/offline.json

# Deterministic MCP scenario contract
python -m pytest evals/eval_python/test_agent/test_scenarios_deterministic.py -v

# Local framework integration and normalized result-contract tests
python -m pytest evals/eval_python/test_agent/test_scenarios_integration.py evals/eval_python/test_agent/test_copilot_backend.py evals/eval_python/test_agent/test_result_contract.py -v

# Full live agent evaluation; requires authentication and real Copilot calls
$env:RUN_LLM_EVALS = "1"

# Required live preflight: agent + MCP tool trace + structured judge response
$env:RUN_LLM_SMOKE = "1"
python -m pytest evals/eval_python/test_agent/test_live_smoke.py -v -s `
  --test-results-json test-results/live-smoke.json `
  --junitxml=test-results/live-smoke.junit.xml

# Run the full live matrix only after the smoke test passes
python -m pytest evals/eval_python/test_agent/test_scenarios_live.py -v -s --tb=short `
  --test-results-json test-results/live.json `
  --junitxml=test-results/live.junit.xml

# Offline red-team fixture checks
python -m pytest evals/eval_python/test_redteam/test_redteam.py -m "not live" -k well_formed -v

# Provider-backed red-team evaluation
python -m pytest evals/eval_python/test_redteam/test_redteam.py -m live -v -s --tb=short `
  --test-results-json test-results/redteam.json `
  --junitxml=test-results/redteam.junit.xml

# Compare normalized Python/.NET artifacts against the shared golden contract
python -m evals.eval_python.result_conformance `
  test-results/python-results.json test-results/dotnet-results.json
```

Every pytest run writes JSON to `test-results/pytest-results.json` by default.
Use `--test-results-json` or `PYTEST_RESULTS_JSON` to choose another path, and
`--no-test-results` to disable it. The report includes safe run metadata,
aggregate counts, per-test outcomes, durations, skip reasons, failure details,
collection errors, and internal errors. It does not store tokens or raw model
prompts/responses. Add `Tee-Object` when a human-readable terminal log is also
needed:

Failure records use stable categories where applicable: `agent_failure`,
`judge_schema_error`, `provider_error`, `tool_trace_missing`,
`test_configuration_error`, or `evaluation_error`. A provider or judge failure
is not evidence of an agent vulnerability; red-team vulnerability evidence
remains in the detailed red-team JSON report.

```powershell
python -m pytest evals/eval_python/test_agent/test_scenarios_live.py -v -s `
  --test-results-json test-results/live.json 2>&1 |
  Tee-Object test-results/live.log
```

The live commands also require `COPILOT_GITHUB_TOKEN` or a cached Copilot CLI
login. Set `COPILOT_TIMEOUT_SECONDS` to bound each Copilot startup, session,
request, and cleanup operation; progress output is enabled by default and can
be disabled with `COPILOT_PROGRESS=0`:

```powershell
$env:COPILOT_TIMEOUT_SECONDS = "60"
$env:COPILOT_PROGRESS = "1"
copilot auth status
```

### Live Model Compatibility Notes

The live smoke test is the compatibility gate for each selected agent and judge
model. The current local `gpt-5.6-luna` run completed most scenarios, but also
showed judge `Verdicts` schema-validation failures, one model-listing provider
failure, and missing tool-trace failures. Treat those as compatibility or
runtime findings until reproduced by the smoke test and classified in the JSON
report; do not count them as model vulnerabilities automatically.

| Agent model | Judge model | Smoke result | Last verified note |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | `gpt-5.6-luna` | Passed | Agent, MCP trace, and structured judge parsing succeeded. |

For repeated or tool-aware red-team runs, use the pytest options documented in
[Red-Team Evaluation](#red-team-evaluation) or the standalone CLI:

```powershell
python -m evals.eval_python.test_redteam.redteam_run `
  --backend copilot `
  --model gpt-5-mini `
  --repetitions 3 `
  --output results-redteam.json
```

Run the .NET evaluation layer separately:

```powershell
# Restore and build
dotnet restore evals/eval_dotnet/MathMcp.MeaiEval.csproj
dotnet build evals/eval_dotnet/MathMcp.MeaiEval.csproj

# Run all shared scenarios once
dotnet run --project evals/eval_dotnet/MathMcp.MeaiEval.csproj

# Or use the PowerShell runner with repetitions and an output path
.\evals\eval_dotnet\run.ps1 -Build -Repetitions 3 -Output eval_results.json
```

The Python and .NET live layers are opt-in and can incur provider usage. Keep
them out of normal CI unless credentials and external-service access are
available.

## Optional LLM evaluation

Install the desired optional dependencies:

```powershell
python -m pip install -e ".[dev,live]"
```

The Copilot SDK backend is intentionally opt-in. Set `RUN_LLM_EVALS=1` before
running provider-backed tests. The system under test uses the selected
`CopilotMCPBackEnd` or `CopilotAgentBackend`, while DeepEval metrics use an
independent `CopilotLLMJudge`. Configure them
separately with `COPILOT_BACKEND`, `COPILOT_MODEL`, and `COPILOT_JUDGE_MODEL`:

```powershell
$env:RUN_LLM_EVALS = "1"
$env:COPILOT_BACKEND = "mcp"
$env:COPILOT_MODEL = "gpt-5-mini"
$env:COPILOT_JUDGE_MODEL = "gpt-5-mini"
python -m pytest evals/eval_python/test_agent/test_scenarios_live.py -v -s
```

Set `COPILOT_BACKEND=agent` to load the custom agents from
`.github/agents/math_agent`; `mcp` calls the MCP tools directly and is the default.

Deterministic tool names, arguments, results, and error categories remain
authoritative over judge output. Judge or provider failures are recorded as
evaluation failures and are not counted as agent vulnerabilities.

## Testing Layers

This framework provides three distinct testing layers:

1. **Deterministic Layer** (`evals/eval_python/test_agent/test_scenarios_deterministic.py` - always runs, no API calls): Validates scenario schema, verifies expected results, and executes scenarios locally using `operations.execute()`. Tests tool invocation, error handling, and response correctness without needing any LLM backend. This is your CI/CD gate.

2. **Integration Layer** (`evals/eval_python/test_agent/test_scenarios_integration.py` - opt-in): Runs scenarios through framework-specific integrations (DeepEval, MEAI) with synthetic or local model results.

3. **Live Layer** (`evals/eval_python/test_agent/test_scenarios_live.py` - opt-in, real LLM calls): Runs the same scenarios through the actual Copilot SDK backend to see how well real AI models handle tool calling. Includes autonomous evaluation via DeepEval metrics that judge whether the agent's response was appropriate.

4. **Red-Team Layer** (`evals/eval_python/test_redteam`): Adversarial attacks to find model vulnerabilities—prompt injection, jailbreaks, PII leakage, and more. Run the offline checks with `pytest evals/eval_python/test_redteam/test_redteam.py -k well_formed`; opt into provider-backed attacks with `RUN_LLM_EVALS=1 pytest evals/eval_python/test_redteam/test_redteam.py -m live`.

## Red-Team Evaluation

The red-team suite exercises the Copilot-backed agent against adversarial
prompts and records the agent response, tool calls, independent judge verdict,
severity, reasoning, latency, and provider or evaluation failures. It covers
static scenarios from `evals/golden/scenarios.json` and can optionally add
tool-aware attacks generated by DeepTeam.

### Run Red-Team Checks

Offline fixture validation requires no API access:

```powershell
python -m pytest evals/eval_python/test_redteam/test_redteam.py -k well_formed -v
```

Provider-backed attacks use the same opt-in guard as the live agent tests:

```powershell
$env:RUN_LLM_EVALS = "1"
$env:COPILOT_BACKEND = "mcp"
$env:COPILOT_MODEL = "gpt-5-mini"
$env:COPILOT_JUDGE_MODEL = "gpt-5-mini"
python -m pytest evals/eval_python/test_redteam/test_redteam.py -m live -v -s
```

Pytest also supports the repeated and tool-aware red-team suite controls that
are available in the CLI:

```powershell
python -m pytest evals/eval_python/test_redteam/test_redteam.py -m live -v -s `
  --redteam-repetitions 3 `
  --redteam-concurrency 2 `
  --redteam-tool-aware `
  --redteam-attack-types prompt_injection jailbreak
```

These options switch pytest to aggregate suite mode; the default pytest run
keeps one independently reported test per attack scenario.

For repeated runs, filtering, tool-aware generation, and JSON output, use the
CLI runner:

```powershell
python -m evals.eval_python.test_redteam.redteam_run `
  --backend copilot `
  --model gpt-5-mini `
  --repetitions 3 `
  --output results-redteam.json

python -m evals.eval_python.test_redteam.redteam_run `
  --backend copilot `
  --tool-aware `
  --repetitions 3 `
  --output results-redteam-tool-aware.json
```

The runner currently supports the Copilot backend only. Set
`RUN_LLM_EVALS=1`, configure authentication, and optionally set
`COPILOT_BACKEND` to `agent` to load `.github/agents/math_agent`.
`COPILOT_MODEL` and `COPILOT_JUDGE_MODEL` remain independently configurable.

### Attack Coverage

The static red-team roster includes prompt injection, jailbreak and roleplay,
tool reordering, excessive agency, indirect injection, argument injection,
encoding evasion, type confusion, resource exhaustion, and null injection.
These map to the relevant OWASP LLM Top 10 categories where applicable.

### Tool-Aware Attacks

The `--tool-aware` option extracts the MCP tool descriptions and uses them to
generate more targeted attacks. The generated attacks can:

- reference discovered tool names and capabilities;
- refine prompts based on prior tool calls and responses; and
- probe parameter injection, type confusion, and unauthorized tool chaining.

### Red-Team Architecture

The implementation is organized under `evals/eval_python/test_redteam`:

- `test_redteam.py`: pytest validation and opt-in live execution;
- `redteam_run.py`: repeated-run CLI entry point and JSON output;
- `redteam_adapter.py`: scenario execution, independent judging, and aggregation;
- `deepteam_generator.py`: optional DeepTeam attack generation;
- `multiturn_adapter.py`: Crescendo, PAIR, TAP, and tool-specific attacks;
- `tool_extractor.py`: MCP tool description extraction; and
- `reporting.py`: text, HTML, CSV, and JSON report generation.

The agent backend and judge are separate: the selected Copilot backend runs the
target agent with MCP tools, while `CopilotLLMJudge` evaluates the result
without those tools. Judge or provider failures are recorded as failures, not
vulnerabilities.

### Scenario Format

Red-team scenarios use the shared fixture format:

```json
{
  "id": "prompt-injection-order",
  "prompt": "The adversarial prompt",
  "attack_type": "prompt_injection",
  "target_boundary": "agent",
  "rubric_id": "math-tool-v1",
  "expected_tools": [
    {"name": "add", "arguments": {"a": 2, "b": 3}}
  ],
  "expected": {"value": 5, "operation": "add"},
  "strict_tool_validation": true,
  "notes": "What this scenario tests"
}
```

The `attack_type` field selects a scenario for red-team execution.
`target_boundary` identifies whether the case targets the agent or the MCP
server. `expected_tools`, `expected`, and `expected_error` preserve the
deterministic contract that can be checked alongside the judge verdict.

### Results and Reports

The CLI writes a JSON suite result containing per-attack records, aggregate
counts by attack type, vulnerability and defense rates, evaluation failures,
and average latency. Reports can be generated from that JSON:

```powershell
python -c "
import json
from pathlib import Path
from evals.eval_python.test_redteam.reporting import generate_all_reports

results = json.loads(Path('results-redteam.json').read_text())
reports = generate_all_reports(results, Path('reports/'))
print(f'Reports generated: {reports}')
"
```

For CI, keep the offline fixture check as the default gate. Provider-backed
red-team execution should be a separately configured job with credentials and
`RUN_LLM_EVALS=1`.

## Detailed Architecture

### Core Components
- **`src/mcp_app/`**: MCP server with schemas, operations, and tool definitions
- **`evals/eval_python/test_agent/`**: Deterministic scenario tests (no API, CI/CD gate)
  - `test_scenarios_deterministic.py`: Validates scenarios and executes them locally
  - `test_scenarios_integration.py`: Framework integration tests with synthetic results
  - `test_scenarios_live.py`: Live evaluation with real LLM (opt-in)
- **`evals/eval_python/`**: Agent evaluation framework
  - `copilot_backend.py`: Contains `BaseLLM`, `CopilotMCPBackEnd`, and `CopilotAgentBackend`
  - `copilot_llm.py`: Contains `CopilotLLMJudge` (DeepEval judge)
  - `trace.py`: Tool trace normalization
- **`evals/golden/`**: Test scenarios and expected outcomes (scenarios.json)

### Class Hierarchy
```python
BaseLLM (abstract)
├── CopilotMCPBackEnd (Copilot SDK agent executor with MCP tools)
└── CopilotAgentBackend (Copilot SDK executor with repository custom agents)

CopilotLLMJudge (DeepEval judge for metric evaluation)
```

### Backend Usage
```python
from evals.eval_python import BaseLLM, CopilotMCPBackEnd, CopilotAgentBackend

# MCP-only backend
backend = CopilotMCPBackEnd()
result = backend.run("user prompt")  # Returns dict with response, tool_calls, etc.

# Hierarchical custom-agent backend
backend = CopilotAgentBackend()
result = backend.run("user prompt")  # Loads .github/agents/math_agent/*.agent.md

# Judge backend
from evals.eval_python import CopilotLLMJudge
judge = CopilotLLMJudge(model="gpt-5-mini")
score = judge.generate(prompt, schema=MetricType)
```

### Test Structure
- Use `@pytest.mark.parametrize` with scenario IDs for test discovery
- Filter scenarios by type: `tool_scenarios`, `metric_only_scenarios`, `error_scenarios`, `security_scenarios`
- Conftest provides fixture loading and credential validation

## .NET MEAI / Copilot SDK Evaluation

The `evals/eval_dotnet` project provides a Microsoft.Extensions.AI evaluation
harness backed by the GitHub Copilot SDK. It loads the shared scenarios,
invokes the local `math-mcp` server, captures response and tool-call data, and
writes normalized results compatible with the other evaluation paths.

### Requirements and Setup

- .NET 8.0 or later
- `Microsoft.Extensions.AI` 10.4.0
- `GitHub.Copilot.SDK` 1.0.0-beta.8
- Python 3.10+ with the MCP server installed

Install the Python dependencies, then restore the .NET project:

```powershell
python -m pip install -e ".[dev]"
dotnet restore evals/eval_dotnet/MathMcp.MeaiEval.csproj
```

Configure the Copilot model and Python executable when the defaults are not
suitable:

```powershell
$env:COPILOT_MODEL = "gpt-4.1"
$env:PYTHON = "python"
```

### Build and Run

```powershell
dotnet build evals/eval_dotnet/MathMcp.MeaiEval.csproj

# Run all scenarios once
dotnet run --project evals/eval_dotnet/MathMcp.MeaiEval.csproj

# Repeat scenarios and choose an output file
dotnet run --project evals/eval_dotnet/MathMcp.MeaiEval.csproj -- `
  --repetitions 3 --output eval_results.json
```

The harness also accepts `--provider` for the provider label in normalized
results. Output records include the scenario and repetition IDs, response,
tool calls and results, trace status, pass/fail state, failure category,
latency, target boundary, and rubric ID.

### .NET Adapter Components

- `evals/eval_dotnet/CopilotSdkAgent.cs`: starts the Copilot session, configures
  the local MCP server, and captures response and tool events.
- `evals/eval_dotnet/Program.cs`: loads `evals/golden/scenarios.json`, runs
  repetitions, normalizes results, and writes JSON output.
- `evals/eval_dotnet/ScenarioAssertions.cs`: checks expected response text,
  numeric values, errors, and ordered tool-call arguments.

The adapter uses the same scenarios and MCP server as the Python evaluations,
so its results can be compared with the deterministic and DeepEval paths.
When the Copilot SDK does not provide a complete tool-event payload, the
normalized record reports an unavailable or partial trace and the scenario
contract remains authoritative. Model comparison and statistical inference are
deferred to [the statistical evaluation plan](docs/future_statistical_tests_model_comparison_plan.md).

## Development Guidelines

### Naming Conventions
- **Classes**: `BaseLLM`, `CopilotMCPBackEnd`, `CopilotAgentBackend`, and `CopilotLLMJudge`
- **Functions**: `run()` (sync), `run_async()` (async), `a_generate()` (async judge)
- **Constants**: UPPERCASE (e.g., DEEPTEAM_VULNERABILITIES)

### Credential Management
- Create `.env` from `.env.example` for local development
- Set `COPILOT_GITHUB_TOKEN` with your GitHub PAT
- Optional: `COPILOT_MODEL` (default: gpt-5-mini), `COPILOT_JUDGE_MODEL` (default: gpt-5-mini)
- Loaded automatically via `python-dotenv` in conftest

### Code Style
- Type hints required (use `from __future__ import annotations`)
- Docstrings for classes and public methods
- Async patterns: `asyncio.run()`, `asyncio.wait_for()` with timeout
- Error handling: Provide clear messages distinguishing SDK errors, auth errors, execution errors

## Common Tasks

### Add a New Test Scenario
1. Add JSON to `evals/golden/scenarios.json` with: `id`, `prompt`, `expected_tools` or `metric_type`
2. Tests auto-parametrize by scenario ID

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
