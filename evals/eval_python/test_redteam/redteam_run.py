"""DeepEval red-team evaluation runner for agent security testing.

Usage:
    python -m evals.eval_python.test_redteam.redteam_run \\
        --scenarios evals/golden/scenarios.json \
        --output results-redteam.json \\
        --attack-types prompt_injection jailbreak \\
        --backend copilot \\
        --model gpt-5

Red-team attack types:
    - prompt_injection: Direct system override attempts
    - jailbreak: Roleplay, DAN, and bypass attempts
    - tool_reordering: Tool sequence manipulation
    - excessive_agency: Unauthorized scope expansion
    - indirect_injection: Malicious content via context
    - argument_injection: Payload in tool arguments
    - encoding_evasion: Base64, ROT13, other encoding
    - type_confusion: Type mismatch and validation bypass
    - resource_exhaustion: Boundary conditions, integer overflow
    - null_injection: Null/nil value handling
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def positive_int(value: str) -> int:
    """Parse a strictly positive command-line integer."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run red-team evaluation on agent security"
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/golden/scenarios.json"),
        help="Path to scenarios fixture file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results-redteam.json"),
        help="Output file for red-team results",
    )
    parser.add_argument(
        "--attack-types",
        type=str,
        nargs="*",
        help="Specific attack types to test (e.g., prompt_injection jailbreak)",
    )
    parser.add_argument(
        "--repetitions",
        type=positive_int,
        default=1,
        help="Number of times to run each attack",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["copilot"],
        default="copilot",
        help="Backend to use for evaluation",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("COPILOT_MODEL", "gpt-5"),
        help="Model to use (default varies by backend)",
    )
    parser.add_argument(
        "--concurrency",
        type=positive_int,
        default=1,
        help="Concurrent evaluation runs",
    )
    parser.add_argument(
        "--severity-threshold",
        type=str,
        choices=["critical", "high", "medium", "low", "info"],
        default="low",
        help="Minimum severity to report",
    )
    parser.add_argument(
        "--tool-aware",
        action="store_true",
        help="Enable tool-aware attack generation (reads tool descriptions)",
    )

    args = parser.parse_args()

    if os.environ.get("RUN_LLM_EVALS") != "1":
        print("Set RUN_LLM_EVALS=1 to run provider-backed red-team evaluations.")
        sys.exit(2)

    # Load scenarios
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    print(f"Loaded {len(scenarios)} scenarios from {args.scenarios}")

    # Filter to red-team scenarios if attack-types specified
    redteam_scenarios = [s for s in scenarios if s.get("attack_type")]
    if args.attack_types:
        redteam_scenarios = [
            s for s in redteam_scenarios if s.get("attack_type") in args.attack_types
        ]

    if not redteam_scenarios:
        print("No red-team scenarios found.")
        sys.exit(1)

    print(
        f"Running {len(redteam_scenarios)} red-team scenario(s) "
        f"with {len(set(s.get('attack_type') for s in redteam_scenarios))} attack type(s)"
    )

    # Extract tool context if enabled
    tools_context = None
    tools_info = None
    if args.tool_aware:
        print("Extracting tool descriptions for tool-aware attacks...")
        try:
            from .tool_extractor import extract_tools_from_mcp, format_tools_for_context
            tools_info = extract_tools_from_mcp()
            tools_context = format_tools_for_context(tools_info)
            print(f"Extracted {len(tools_info)} tools for tool-aware attack generation")
            if tools_info:
                print(f"Available tools: {', '.join(tools_info.keys())}")
        except Exception as e:
            print(f"Warning: Could not extract tools: {e}")
            print("Continuing without tool-aware attacks...")

    # Run red-team evaluation with selected backend
    try:
        from .redteam_adapter import run_redteam_suite

        # Initialize backend based on selection
        if args.backend == "copilot":
            from evals.eval_python.copilot_backend import CopilotLLM
            from evals.eval_python.copilot_llm import CopilotLLMJudge
            from .redteam_adapter import (
                CopilotRedTeamEvaluator,
            )

            backend = CopilotLLM(model=args.model)
            judge = CopilotLLMJudge(
                model=os.environ.get("COPILOT_JUDGE_MODEL", args.model)
            )

            def evaluator_class(*, attack_type: str) -> CopilotRedTeamEvaluator:
                return CopilotRedTeamEvaluator(
                    attack_type=attack_type,
                    judge=judge,
                )
        else:
            raise ValueError(f"Unknown backend: {args.backend}")

        suite_result = run_redteam_suite(
            redteam_scenarios,
            backend,
            evaluator_class,
            attack_types=args.attack_types,
            repetitions=args.repetitions,
            concurrency=args.concurrency,
            severity_threshold=args.severity_threshold,
            framework_version=get_deepeval_version(),
            tools_context=tools_context,
            tools_info=tools_info,
        )

        # Print summary
        summary = suite_result.get("summary", {})
        print(f"\n=== Red-Team Evaluation Summary ===")
        print(f"Total attacks: {suite_result['total_runs']}")
        print(f"Vulnerabilities found: {summary.get('total_vulnerabilities_found', 0)}")
        print(f"Defended successfully: {summary.get('total_defended', 0)}")
        print(f"Overall vulnerability rate: {summary.get('overall_vulnerability_rate', 0):.1%}")
        print(f"Overall defense rate: {summary.get('overall_defense_rate', 0):.1%}")

        print(f"\nBy attack type:")
        for attack_type, agg in suite_result.get("by_attack_type", {}).items():
            print(
                f"  {attack_type}: {agg['vulnerabilities_found']}/{agg['attack_count']} "
                f"vulnerabilities ({agg['vulnerability_rate']:.1%})"
            )

    except Exception as e:
        print(f"Error running red-team evaluation: {e}")
        sys.exit(1)

    # Save results
    args.output.write_text(json.dumps(suite_result, indent=2), encoding="utf-8")
    print(f"\nResults saved to {args.output}")


def get_deepeval_version() -> str:
    """Get DeepEval version string."""
    try:
        import deepeval

        return deepeval.__version__
    except (ImportError, AttributeError):
        return "unknown"


if __name__ == "__main__":
    main()
