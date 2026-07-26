# MCP Tool-Calling Evaluation Boilerplate

## 1. Objective

Create a small, reproducible repository for testing LLM tool selection and tool-call execution. The domain is intentionally trivial mathematics so that failures are attributable to the model, protocol wiring, or evaluation framework rather than business logic.

The repository will contain one shared implementation:

- `src/`: the common MCP server, operation layer, schemas, and evaluation helpers.
- `tests/`: deterministic unit, protocol, fixture, and adapter-contract tests.
- `evals/`: optional framework-specific LLM evaluation adapters and examples, including `evals/deepeval` and `evals/meaieval`.

The first release is an illustrative testbed, not a production calculator or a statistically representative benchmark. It must support controlled repeated-run comparisons of configured models without overstating conclusions. Every example must be runnable with a local model/API configuration and must also support deterministic, model-free tests.

### Goals

- **Reproducibility:** A contributor can run the deterministic suite offline, with no API key, and obtain the same normalized outcome for a given fixture set.
- **Shared contract:** The MCP server, fixtures, deterministic runner, and evaluation adapters use one repository-level contract. Contract changes require synchronized schemas, fixtures, expected results, and tests.
- **Diagnosability:** Evaluation output records the scenario, planned and executed tool calls, tool results or error categories, final response, and relevant runtime configuration so a failure can be attributed to planning, invocation, server behavior, or evaluation assertions.
- **Extensibility:** Adding a tool, scenario, or evaluation adapter changes the smallest relevant layer and preserves deterministic coverage for the existing shared contract.

## 2. Scope and non-goals

### In scope

- MCP tools for `add`, `subtract`, `multiply`, `divide`, `power`, `exp`, and `log`.
- A common tool contract implemented by the repository-level MCP server.
- Direct unit tests for tool behavior and protocol-level tests that exercise tool discovery and invocation.
- Agent scenarios that test tool selection, argument construction, multi-step calls, errors, and refusal to invent unsupported tools.
- A provider-neutral agent backend and LLM-judge contract, with GitHub Copilot SDK as the LLM backend.
- Optional DeepEval and MEAI adapters under `evals/deepeval` and `evals/meaieval`, over the same scenarios, traces, and normalized results. The DeepEval adapter is Python; the MEAI adapter is .NET.
- GitHub Copilot SDK and Copilot CLI helpers for the system under test and an independently configured LLM judge.
- JSON test fixtures consumed by the shared deterministic runner and all adapters.
- Framework-native repeated-run evaluation through DeepEval and MEAI capabilities.

### Out of scope for the first version

- Streaming, authentication, persistence, user accounts, or deployment infrastructure.
- A custom LLM, custom evaluator model, or claims about statistical model quality.
- Fuzzy numeric behavior in the MCP servers. Numerical operations must be deterministic; tolerance belongs in the evaluator/test assertion.
- Adding every evaluation framework. Each framework gets a small adapter over the same scenario and result schema.

## 3. Repository layout

The target layout is:

```text
docs/plan.md
fixtures/
  scenarios.json
  expected-results.json
src/
	mcp_app/
		__init__.py
		server.py
		operations.py
		schemas.py
tests/
	contracts/
	mcp_app/
	model_free/
	deepeval/
	meaieval/
	evals/
	run_scenarios.py
	deepeval/
		copilot_backend.py
		adapter.py
		run.py
	meaieval/
		copilot_backend.py
		adapter.py
		run.py
README.md
CONTRIBUTING.md
```

All evaluation frameworks use the single repository-level `src/mcp_app` server boundary. Framework-specific adapters and tests live under `evals/deepeval` and `evals/meaieval`; shared protocol and model-free checks live under `tests/mcp_app`, `tests/contracts`, and `tests/model_free`. Copilot SDK integration helpers belong in the relevant `evals/<framework>/` directory.

## 4. Common tool contract

### Inputs and outputs

Each tool accepts JSON object arguments containing finite JSON numbers. The canonical fields are:

| Tool | Required arguments | Result |
| --- | --- | --- |
| `add` | `a`, `b` | `a + b` |
| `subtract` | `a`, `b` | `a - b` |
| `multiply` | `a`, `b` | `a * b` |
| `divide` | `a`, `b` | `a / b` |
| `power` | `base`, `exponent` | `base ** exponent` |
| `exp` | `x` | `e ** x` |
| `log` | `x`, optional `base` | natural log when `base` is omitted; otherwise log to `base` |

Return a structured object with `value` and `operation`. For example:

```json
{"value": 5, "operation": "add"}
```

Tool descriptions must explicitly state the operation, required arguments, units (none), and relevant domain constraints. Argument schemas must reject missing, extra, non-numeric, NaN, and infinite values before execution.

### Error behavior

Use stable error categories in the shared implementation:

- `invalid_arguments`: schema/type/range failure.
- `division_by_zero`: `divide` with `b == 0`.
- `domain_error`: `log(x)` with `x <= 0`, invalid logarithm base, or an unsupported real-valued `power` result.
- `non_finite_result`: the operation overflowed or produced a non-finite result.

Errors must be returned through the MCP error mechanism with the category and a human-readable message. Do not silently coerce invalid input or return `null` as a successful result.

### Numeric policy

- Use IEEE-754 double precision in the shared implementation.
- Reject non-finite inputs.
- Use a relative/absolute tolerance of `1e-9` for ordinary results in tests.
- Test overflow and domain boundaries explicitly rather than relying on platform-specific exception text.

## 5. Implementation sequence

1. **Repository bootstrap**
	- Add the repository-level Python package metadata and root README.
	- Document the supported Python version, dependency installation, environment variables, and commands.
	- Add formatting, linting, and test configuration.
2. **Pure operation layer**
	- Implement the seven operations independently of MCP transport.
	- Centralize validation and error mapping so direct tests and MCP handlers use the same behavior.
3. **MCP server layer**
	- Register exactly the seven tools with the canonical names and schemas.
	- Provide a stdio entry point for local clients and tests. Keep transport setup separate from operation logic.
	- Add a tool-list test that verifies names and required schema fields.
4. **Shared fixtures**
	- Create `fixtures/scenarios.json` with stable IDs, user prompts, expected tool calls, arguments, and expected final answer facts.
	- Include single-step, multi-step, ambiguous wording, malformed arguments, unsupported request, and domain-error cases.
	- Make fixture execution deterministic by allowing a mocked planner/tool-call sequence.
5. **Evaluation harness**
	- Define one normalized result schema: run ID, scenario ID, model/provider configuration, seed, repetition index, selected tools, arguments, tool results, final response, pass/fail, failure category, and latency if available.
	- Implement a model-free runner first; then add framework-specific adapters that consume the same scenarios and normalized results.
	- Preserve framework-native evaluation records, including per-run scores, pass/fail outcomes, repetition counts, mean and standard deviation where supported, latency, token usage, cost, and model/provider configuration.
	- Add repeated-run evaluation paths using DeepEval and MEAI. Keep the system-under-test model and judge model independently configurable.
	- Add Copilot SDK/CLI adapters that capture session lifecycle, permissions, MCP discovery/invocation, tool traces, idle/error completion, and replay artifacts.
	- Keep API keys and model names in environment variables. Never commit secrets or snapshots containing prompts with secrets.
6. **Documentation and examples**
	- Add one minimal end-to-end example for the shared server and one example per evaluation framework.
	- Explain which assertions are deterministic and which depend on an LLM.
	- Record framework versions, model/provider configuration, seed, run timestamp, and repository revision with every evaluation run.

## 6. Scenario set

The initial fixture must include at least these cases:

| ID | Prompt shape | Expected behavior |
| --- | --- | --- |
| `add-basic` | "What is 2 plus 3?" | Select `add` with `a=2`, `b=3`; value `5`. |
| `compound-basic` | "Add 2 and 3, then multiply the result by 4." | Call `add`, then `multiply` using the prior result; value `20`. |
| `log-default-base` | "What is the natural log of 1?" | Select `log` with `x=1`; value `0`. |
| `divide-zero` | "Divide 10 by 0." | Select `divide`; surface `division_by_zero`; do not fabricate a number. |
| `log-domain` | "Calculate log of -1." | Surface `domain_error`. |
| `missing-argument` | Tool call omits `b`. | Reject with `invalid_arguments`. |
| `unsupported-operation` | "Find the derivative of x squared." | Do not select a math tool; clearly state the capability is unsupported. |
| `ambiguous-order` | "Subtract 3 from 10." | Select `subtract` with `a=10`, `b=3`; value `7`. |

Add cases for negative numbers, decimal values, a supplied logarithm base, power precedence, overflow, extra arguments, and an unknown tool before calling the fixture set complete.

## 7. Framework-native evaluation strategy

The first release uses a three-layer design: agent runtime, evaluation adapter, and model/judge provider. Deterministic server and fixture tests remain exact pass/fail checks. Novel statistical inference is deferred to [docs/future_statistical_tests_model_comparison_plan.md](future_statistical_tests_model_comparison_plan.md).

### Agent and judge contracts

- `IAgentBackend`/equivalent executes a scenario and returns a normalized agent trace.
- `IJudgeBackend`/equivalent evaluates that trace against a versioned rubric and returns structured score, verdict, reason, and judge metadata.
- The judge is independently configured from the system under test. Copilot SDK/CLI may provide either role, but never through the same implicit configuration.
- Deterministic tool names, ordering, arguments, numeric results, and error categories are authoritative. A judge cannot override a known contract failure.
- Malformed, unavailable, or timed-out judge output fails closed and is recorded as a provider/evaluation failure.

### Copilot SDK backend capabilities

- Use the GitHub Copilot SDK as the agent/LLM backend and keep its session configuration explicit.
- Capture agent messages, tool calls, MCP events, permissions, lifecycle status, latency, usage, and provider errors in the normalized trace.
- Use the exact Copilot SDK and CLI versions verified during bootstrap.
- Keep live evaluation opt-in and preserve replayable deterministic traces for CI.

### MEAI capabilities

- Use Microsoft.Extensions.AI as the model/tool abstraction boundary for repeated executions.
- Record per-run scores, pass/fail, latency, usage, provider errors, and model configuration in the normalized result.
- Keep the MEAI adapter optional and use synthetic backend results for deterministic CI tests.

### DeepEval capabilities

- Use DeepEval's native test cases and agent metrics, including tool correctness and task completion where applicable.
- Preserve the per-test metric score, threshold, success status, reason, and model/judge configuration in the normalized result.
- Use DeepEval's supported evaluation execution, caching, concurrency, and reporting features for repeated runs; do not claim statistical significance from those reports.
- Keep custom statistical comparisons out of the DeepEval adapter until the future statistical plan is approved.

### Required framework artifacts

- Native framework output plus a normalized result record for each scenario and repetition.
- A framework-generated summary containing pass rates or scores, run counts, and available performance data.
- A Markdown or JSON export that identifies the framework version, model/provider configuration, fixture revision, and limitations of descriptive results.

## 8. Test strategy

### Required automated checks

- Unit tests cover every operation's normal, boundary, invalid-input, and error-category behavior.
- MCP contract tests verify tool discovery, schemas, valid invocation, malformed invocation, and error propagation.
- Fixture tests run all scenarios against the shared implementation and compare normalized results.
- Evaluation adapter tests use a fake model/planner and do not make network calls.
- Framework-adapter tests use fake model/planner results to verify native score extraction, repetition metadata, model configuration, and report normalization without network calls.
- A smoke test starts each stdio server, lists tools, invokes `add`, and shuts it down cleanly.

### CI gates

Every pull request must run:

```text
Python: install locked dependencies, format check, lint, type check, pytest
Deterministic: execute the shared fixtures and compare normalized output
```

LLM-backed evaluations are opt-in, excluded from the required CI gate, and must fail clearly when credentials are absent. Set a fixed seed where the selected provider supports it and store the model/provider configuration in the result artifact.

Framework-native repeated runs and model comparisons run as an explicit opt-in job or local command. CI must validate adapters with synthetic results; live model comparisons must record the model configuration and fixture/repository revisions and must not block the deterministic gate unless a comparison is intentionally promoted to a release check.

## 9. Definition of done

- A new contributor can install the repository from the README and run the local tests without an API key.
- The shared server exposes exactly the seven canonical tools and schemas.
- All required scenarios pass deterministically against the shared server.
- Invalid input and mathematical domain errors are categorized consistently.
- DeepEval and MEAI adapters consume the same normalized harness output, with Copilot SDK helpers providing the LLM backend.
- GitHub Copilot SDK/CLI can run the agent under test and an independently configured judge.
- Framework-native repeated-run evaluation produces raw and aggregate artifacts for at least two model/provider configurations using the same fixtures.
- MEAI demonstrates repeated evaluation using normalized score, latency, usage, and provider outputs where supported.
- DeepEval demonstrates native agent metrics and normalized per-test results without introducing custom statistical significance claims.
- CI runs formatting, static checks, unit tests, protocol tests, and shared deterministic fixtures.
- The README explains how to add a tool, a scenario, and an evaluation adapter without editing unrelated layers.

## 10. Decisions to confirm during implementation

- Pin the minimum supported Python version based on the chosen MCP SDK release.
- Select and pin the exact DeepEval, Microsoft.Extensions.AI, GitHub Copilot SDK, and Copilot CLI versions after validating their current APIs; record the choice in the repository package manifest.
- Decide whether framework adapters live under `evals/` or in separate optional dependency groups. The default is optional groups so deterministic tests stay lightweight.
- Pin the selected DeepEval and Microsoft.Extensions.AI versions and confirm their native APIs before implementation.
- Decide the default framework-native repetition count, success/score thresholds, and policy for provider failures, timeouts, and unavailable seeds.
- Review [docs/future_statistical_tests_model_comparison_plan.md](future_statistical_tests_model_comparison_plan.md) separately before adding custom statistical inference.
- If a framework cannot represent MCP natively, adapt at the normalized tool-call boundary rather than changing the server contract.
