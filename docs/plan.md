# MCP Tool-Calling Evaluation Boilerplate

## 1. Objective

Create a small, reproducible repository for testing LLM tool selection and tool-call execution. The domain is intentionally trivial mathematics so that failures are attributable to the model, protocol wiring, or evaluation framework rather than business logic.

The repository will contain two equivalent implementations:

- `python/`: Python MCP server and evaluation examples.
- `csharp/`: .NET MCP server and evaluation examples.

The first release is an illustrative testbed, not a production calculator or an attempt to benchmark models scientifically. Every example must be runnable with a local model/API configuration and must also support deterministic, model-free tests.

## 2. Scope and non-goals

### In scope

- MCP tools for `add`, `subtract`, `multiply`, `divide`, `power`, `exp`, and `log`.
- A common tool contract and equivalent behavior in both language tracks.
- Direct unit tests for tool behavior and protocol-level tests that exercise tool discovery and invocation.
- Agent scenarios that test tool selection, argument construction, multi-step calls, errors, and refusal to invent unsupported tools.
- Initial adapters/examples for DeepEval and AgentEval (or the current equivalent framework chosen during implementation).
- JSON test fixtures so the same scenarios can be compared across Python and C#.

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
python/
  pyproject.toml
  src/math_mcp/
	 __init__.py
	 server.py
	 operations.py
	 schemas.py
  tests/
	 test_operations.py
	 test_server.py
  evals/
	 run_scenarios.py
	 deepeval_example.py
	 agent_eval_example.py
csharp/
  MathMcp.sln
  src/MathMcp.Server/
  tests/MathMcp.Server.Tests/
  evals/MathMcp.Evals/
README.md
CONTRIBUTING.md
```

The Python and C# servers may use different framework idioms, but their exposed tool names, input fields, output meaning, error categories, and fixture IDs must remain equivalent.

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

Use stable error categories in both implementations:

- `invalid_arguments`: schema/type/range failure.
- `division_by_zero`: `divide` with `b == 0`.
- `domain_error`: `log(x)` with `x <= 0`, invalid logarithm base, or an unsupported real-valued `power` result.
- `non_finite_result`: the operation overflowed or produced a non-finite result.

Errors must be returned through the MCP error mechanism with the category and a human-readable message. Do not silently coerce invalid input or return `null` as a successful result.

### Numeric policy

- Use IEEE-754 double precision in both tracks.
- Reject non-finite inputs.
- Use a relative/absolute tolerance of `1e-9` for ordinary results in tests.
- Test overflow and domain boundaries explicitly rather than relying on platform-specific exception text.

## 5. Implementation sequence

1. **Repository bootstrap**
	- Add the directory structure, Python package metadata, .NET solution, and root README.
	- Document supported Python and .NET versions, dependency installation, environment variables, and commands.
	- Add formatting, linting, and test configuration for each language.
2. **Pure operation layer**
	- Implement the seven operations independently of MCP transport.
	- Centralize validation and error mapping so direct tests and MCP handlers use the same behavior.
3. **MCP server layer**
	- Register exactly the seven tools with the canonical names and schemas.
	- Provide a stdio entry point for local clients and tests. Keep transport setup separate from operation logic.
	- Add a tool-list test that verifies names and required schema fields.
4. **Cross-language fixtures**
	- Create `fixtures/scenarios.json` with stable IDs, user prompts, expected tool calls, arguments, and expected final answer facts.
	- Include single-step, multi-step, ambiguous wording, malformed arguments, unsupported request, and domain-error cases.
	- Make fixture execution deterministic by allowing a mocked planner/tool-call sequence.
5. **Evaluation harness**
	- Define one normalized result schema: scenario ID, selected tools, arguments, tool results, final response, pass/fail, failure category, and latency if available.
	- Implement a model-free runner first; then add framework-specific adapters that consume the same scenarios and normalized results.
	- Keep API keys and model names in environment variables. Never commit secrets or snapshots containing prompts with secrets.
6. **Documentation and examples**
	- Add one minimal end-to-end example per language and one example per evaluation framework.
	- Explain which assertions are deterministic and which depend on an LLM.
	- Record framework versions and model configuration with every evaluation run.

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

## 7. Test strategy

### Required automated checks

- Unit tests cover every operation's normal, boundary, invalid-input, and error-category behavior.
- MCP contract tests verify tool discovery, schemas, valid invocation, malformed invocation, and error propagation.
- Fixture tests run all scenarios against both implementations and compare normalized results.
- Evaluation adapter tests use a fake model/planner and do not make network calls.
- A smoke test starts each stdio server, lists tools, invokes `add`, and shuts it down cleanly.

### CI gates

Every pull request must run:

```text
Python: install locked dependencies, format check, lint, type check, pytest
C#: dotnet restore, format --verify-no-changes, build, test
Cross-language: execute deterministic fixtures and compare normalized output
```

LLM-backed evaluations are opt-in, excluded from the required CI gate, and must fail clearly when credentials are absent. Set a fixed seed where the selected provider supports it and store the model/provider configuration in the result artifact.

## 8. Definition of done

- A new contributor can install both tracks from the README and run the local tests without an API key.
- Both servers expose exactly the same seven canonical tools and schemas.
- All required scenarios pass deterministically in Python and C#.
- Invalid input and mathematical domain errors are categorized consistently.
- At least one DeepEval and one AgentEval example run against the normalized harness output.
- CI runs formatting, static checks, unit tests, protocol tests, and cross-language fixtures.
- The README explains how to add a tool, a scenario, and an evaluation adapter without editing unrelated layers.

## 9. Decisions to confirm during implementation

- Pin the minimum supported Python and .NET versions based on the chosen MCP SDK releases.
- Select the exact DeepEval and AgentEval package names and versions after validating their current MCP/tool-calling integrations; record the choice in each package manifest.
- Decide whether framework adapters live under `evals/` or in separate optional dependency groups. The default is optional groups so deterministic tests stay lightweight.
- If a framework cannot represent MCP natively, adapt at the normalized tool-call boundary rather than changing the server contract.
