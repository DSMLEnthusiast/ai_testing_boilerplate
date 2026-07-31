# Repository Improvement Plan

Date: 2026-07-31

## Review Summary

The repository has a compact, well-separated math implementation in `src/mcp_app` and a useful shared scenario corpus. The main risk is not the math code; it is drift in the evaluation harness. Several documented entry points refer to removed packages or missing project files, provider failures can continue into judge evaluation as empty responses, and the Python and .NET paths do not yet enforce the same result contract.

The recommended order is to restore one reliable offline path first, then make live evaluation failures explicit, and only then expand metrics or reporting.

## Implementation Status

Implemented on 2026-07-31:

- Removed the obsolete model-free runner and corrected active documentation paths.
- Added `pyproject.toml`, separated dependency extras, and an offline GitHub Actions workflow.
- Added provider-failure guards, partial trace classification, unmatched event preservation, and cleanup error reporting.
- Added a versioned result JSON Schema and schema validation for the shared Python contract.
- Added structured .NET tool-event capture and numeric token comparison; fixed the .NET package downgrade.
- Restricted Python agent permissions to MCP requests, denied all judge permission requests, isolated concurrent red-team workers, and escaped HTML report values.

Remaining follow-up work:

- Generate and maintain a compatible dependency lock or constraints file.
- Validate every emitted Python and .NET result artifact against the shared schema, including repository and fixture revisions.
- Replace `.NET` `PermissionHandler.ApproveAll` when the SDK exposes or the repository defines a tested MCP-only handler.
- Add cross-runtime fixture conformance tests that assert captured .NET tool arguments and results, not only response text.

## Findings

### P0: Restore a runnable offline baseline

1. **A pre-refactor deterministic runner is still documented.**
   - Evidence: deterministic execution was refactored into `evals/eval_python/test_agent/test_scenarios_deterministic.py`, but `evals/run_scenarios.py` and the README still reference the removed `tests.model_free.scenario_runner` package.
   - Reproduction: `.venv\Scripts\python.exe evals\run_scenarios.py --repetitions 1 --output results.json` fails with `ModuleNotFoundError: No module named 'tests'`; changing Python interpreters cannot resolve a local package that was removed during the refactor.
   - Action: remove the obsolete runner and its README command if pytest is now the sole deterministic entry point. Only migrate the runner to the current layout if standalone JSON output remains a supported requirement; in that case, add a subprocess smoke test for it.

2. **Project documentation describes a layout that is not present.**
   - Evidence: `README.md`, `CONTRIBUTING.md`, and `evals/__init__.py` reference `tests/model_free`, `tests/contracts`, `evals/deepeval`, `evals/meaieval`, and `pyproject.toml`; none are present in the current tree.
   - Action: choose the current `evals/eval_python` and `evals/eval_dotnet` layout as the source of truth, then update all commands and architecture descriptions in one pass. Add a lightweight documentation check that executes or validates referenced local paths.

3. **There is no automated CI gate.**
   - Evidence: no workflow exists under `.github/workflows`.
   - Action: add one Windows or cross-platform workflow that installs pinned dependencies and runs the offline suite. Keep live Copilot and judge tests opt-in and out of pull-request CI.

### P1: Make evaluation outcomes trustworthy

4. **Provider failures are returned as ordinary backend results.**
   - Evidence: `CopilotMCPBackEnd.run_async` catches every exception and returns an empty response with `failure_category="provider_error"`. Live metric tests then pass that empty response to DeepEval without first failing or skipping the metric.
   - Risk: infrastructure failures can be reported as model-quality failures, wasting judge calls and corrupting comparisons.
   - Action: define one explicit backend result contract. Either raise a typed provider exception or require callers to reject any non-null `failure_category` before metric evaluation. Add tests for client start, session creation, send, trace capture, and cleanup failures.

5. **Trace completeness is over-reported.**
   - Evidence: the Python backend sets `trace_status="complete"` after a response even when a tool request has no matching completion event; unmatched completion events are silently discarded.
   - Risk: tool-correctness metrics may evaluate partial traces as complete evidence.
   - Action: classify traces as `complete`, `partial`, `unavailable`, or `provider_error`; preserve unmatched event IDs and stable parse errors. Reject partial traces for deterministic tool assertions.

6. **The .NET evaluator validates response text instead of actual tool behavior.**
   - Evidence: `CopilotSdkAgent.cs` allocates `toolCalls` but never records or returns them. `ScenarioAssertions.ContainsNumber` uses substring matching, so an expected value such as `2` can match `12`.
   - Risk: the .NET path can pass incorrect tool selection or numeric output.
   - Action: subscribe to Copilot SDK tool events, normalize names/arguments/results to the Python schema, and compare structured values with numeric tolerance. Share fixture-level conformance cases across both runtimes.

7. **Normalized result schemas are only nominally shared.**
   - Evidence: `src/mcp_app/contracts.py` defines a minimal `NormalizedRun`, while Python red-team, Python live, the deterministic path, and .NET each emit different fields and failure values.
   - Action: publish a versioned JSON Schema for run results and judge verdicts. Validate every writer against it in offline tests. Include `schema_version`, scenario/rubric IDs, provider/model, trace status, failure category, latency, usage, repetition, and repository revision.

### P2: Improve security and concurrency boundaries

8. **Permission handlers approve every request.**
   - Evidence: both the Python backend/judge and .NET agent use unconditional approval handlers.
   - Risk: future agents or MCP servers could gain capabilities beyond the intended math tools.
   - Action: deny by default and allow only the named math MCP tools required by the scenario. Keep the judge session tool-free and test that it cannot inherit SUT tools.

9. **Concurrent red-team runs share backend and judge instances.**
   - Evidence: `run_redteam_suite` submits jobs to a thread pool while closing over one `agent_backend`; the CLI evaluator also closes over one judge.
   - Risk: SDK clients or judge implementations may not be thread-safe, causing cross-run contamination or intermittent failures.
   - Action: use backend and evaluator factories per job, or document and enforce serialized access. Add a deterministic concurrency test with stateful fakes.

10. **HTML reporting interpolates unescaped result data.**
    - Evidence: `test_redteam/reporting.py` inserts attack types and metadata directly into HTML.
    - Risk: generated reports can execute markup supplied by fixtures or model-derived fields when opened locally.
    - Action: escape all dynamic text with `html.escape` and test hostile strings.

### P3: Consolidate packaging and maintenance

11. **Dependencies are broad and unpinned.**
    - Evidence: runtime and development requirements use open lower bounds; `deepeval[inspect]`, `deepteam`, and the Copilot SDK have no compatibility ceiling or lock.
    - Action: add a real `pyproject.toml` with package metadata and separated optional groups (`dev`, `live`, `redteam`). Pin known-compatible evaluation-library versions in a lock or constraints file and add an API compatibility smoke test.

12. **Tests contain stale names and duplicated orchestration.**
    - Evidence: deterministic-test docstrings still cite `evals/deepeval_v2`; live metric classes duplicate dataset, backend, trace, and judge setup.
    - Action: first correct stale commands. Then extract only the repeated live-scenario execution fixture, keeping metric-specific expectations explicit.

13. **Generated output policy is inconsistent.**
    - Evidence: build artifacts are present in the workspace and `.gitignore` used to ignore the entire `docs` directory, which prevented new review documents from appearing in version control.
    - Action: keep `bin`, `obj`, egg-info, result JSON, caches, and virtual environments ignored; do not ignore source documentation. Add a clean-check step to CI for accidental generated files.

## Delivery Phases

### Phase 1: Offline Reliability

- Remove the stale model-free runner and its documentation, or explicitly migrate it if standalone JSON output is still required.
- Add focused operation tests and a CLI subprocess smoke test.
- Correct README and contributing commands to match the current tree.
- Add CI for the default offline suite.

Exit criteria:

- A clean clone can install dependencies and run one documented command successfully without credentials or network access.
- Every path referenced by the quick-start and contributor test instructions exists.

### Phase 2: Evaluation Integrity

- Introduce typed provider/trace failures and stop judge evaluation when the SUT run failed.
- Track partial and unmatched tool events.
- Add and enforce the versioned normalized-result schema.
- Bring .NET tool capture and assertions to parity with Python.

Exit criteria:

- Provider failures, model failures, deterministic contract failures, and judge failures are distinguishable in output.
- Python and .NET pass the same schema and fixture-conformance tests.

### Phase 3: Security and Reproducibility

- Replace blanket permission approval with a math-tool allowlist.
- Isolate concurrent backend and judge instances.
- Escape HTML report content.
- Add `pyproject.toml`, optional dependency groups, and compatible version constraints.

Exit criteria:

- Offline tests prove judge/SUT separation, permission restrictions, concurrency isolation, and report escaping.
- Dependency installation is reproducible from a clean environment.

### Phase 4: Maintainability

- Remove stale architecture references and duplicated live-test setup.
- Add schema and documentation checks to CI.
- Record repository revision, fixture revision, model, and framework versions in evaluation artifacts.

Exit criteria:

- One architecture description and one result contract are authoritative across docs and implementations.
- Generated reports can be compared across revisions without guessing their provenance.

## Suggested First Pull Request

Keep the first change deliberately small:

1. Remove the obsolete `evals/run_scenarios.py` path and README command, keeping pytest as the deterministic entry point.
2. Correct the remaining stale layout and command references.
3. Add focused operation tests around the existing deterministic suite.
4. Add a CI workflow that runs only those offline checks.

This provides a reliable safety net before changing live SDK, DeepEval, red-team, or .NET behavior.
