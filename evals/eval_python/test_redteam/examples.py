"""Example: Complete Red-Team Evaluation Workflow

This example demonstrates all 5 advanced features:
1. DeepTeam attack generation
2. Multi-turn attack scenarios
3. Performance reporting
4. Vulnerability definitions
5. MCP security testing

Run locally (no API required):
    python evals/deepeval/red_teaming/examples.py --local

With Copilot backend:
    python evals/deepeval/red_teaming/examples.py --backend copilot

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Example 1: DeepTeam Attack Generation
def example_deepteam_generation() -> list[dict[str, Any]]:
    """Generate attacks using DeepTeam RedTeamer."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: DeepTeam Attack Generation")
    print("=" * 80)

    try:
        from .deepteam_generator import generate_attacks_with_deepteam

        print("\nGenerating 2 attacks for each vulnerability type...")
        attacks = generate_attacks_with_deepteam(num_attacks_per_type=2)

        print(f"Generated {len(attacks)} attacks:")
        for attack in attacks[:5]:  # Show first 5
            print(f"\n  Attack: {attack['id']}")
            print(f"  Type: {attack['attack_type']} ({attack['owasp_category']})")
            print(f"  Prompt: {attack['prompt'][:80]}...")

        print(f"\n  ... and {len(attacks) - 5} more attacks")
        return attacks

    except ImportError:
        print("\n⚠️  DeepTeam not installed. Skipping dynamic attack generation.")
        print("    Install with: pip install -e '.[deepeval]'")
        return []


# Example 2: Multi-Turn Attacks
def example_multiturn_attacks(backend: Any | None = None) -> None:
    """Execute multi-turn attack scenarios."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Multi-Turn Attack Scenarios")
    print("=" * 80)

    from .multiturn_adapter import (
        crescendo_attack,
        pair_attack,
        tap_attack,
    )

    if backend is None:
        print("\nMulti-turn attacks require a backend. Skipping live execution.")
        print("Usage with backend:")
        print("  crescendo = crescendo_attack('test', backend, 'Add 2 and 3')")
        return

    # Crescendo attack
    print("\nExecuting Crescendo (gradual escalation) attack...")
    try:
        crescendo = crescendo_attack(
            "crescendo-demo",
            backend,
            "What is 2 + 3?",
        )
        print(f"  Total turns: {crescendo['total_turns']}")
        print(f"  Total tool calls: {crescendo['total_tool_calls']}")
    except Exception as e:
        print(f"  Error: {e}")

    # PAIR attack
    print("\nExecuting PAIR (iterative refinement) attack...")
    try:
        pair = pair_attack(
            "pair-demo",
            backend,
            "Calculate 5 * 4",
            refinement_count=3,
        )
        print(f"  Total turns: {pair['total_turns']}")
        print(f"  Total tool calls: {pair['total_tool_calls']}")
    except Exception as e:
        print(f"  Error: {e}")

    # TAP attack
    print("\nExecuting TAP (tree exploration) attack...")
    try:
        tap = tap_attack(
            "tap-demo",
            backend,
            "Divide 10 by 2",
            branching_factor=2,
            max_depth=2,
        )
        print(f"  Total turns: {tap['total_turns']}")
        print(f"  Total tool calls: {tap['total_tool_calls']}")
    except Exception as e:
        print(f"  Error: {e}")


# Example 3: Reporting and Visualization
def example_reporting() -> None:
    """Generate comprehensive reports."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Reporting and Visualization")
    print("=" * 80)

    # Load sample results
    sample_result = {
        "framework": "DeepEval-RedTeam",
        "framework_version": "0.1.0",
        "total_runs": 30,
        "scenarios_tested": 10,
        "repetitions": 3,
        "attack_types_tested": ["prompt_injection", "jailbreak", "excessive_agency"],
        "summary": {
            "total_vulnerabilities_found": 5,
            "total_defended": 25,
            "overall_vulnerability_rate": 0.167,
            "overall_defense_rate": 0.833,
        },
        "by_attack_type": {
            "prompt_injection": {
                "attack_count": 10,
                "vulnerabilities_found": 3,
                "defended": 7,
                "vulnerability_rate": 0.3,
                "defense_rate": 0.7,
                "avg_latency_ms": 145.2,
            },
            "jailbreak": {
                "attack_count": 10,
                "vulnerabilities_found": 2,
                "defended": 8,
                "vulnerability_rate": 0.2,
                "defense_rate": 0.8,
                "avg_latency_ms": 152.1,
            },
            "excessive_agency": {
                "attack_count": 10,
                "vulnerabilities_found": 0,
                "defended": 10,
                "vulnerability_rate": 0.0,
                "defense_rate": 1.0,
                "avg_latency_ms": 138.5,
            },
        },
        "results": [],
    }

    from .reporting import (
        generate_all_reports,
        generate_text_report,
    )

    report_dir = Path("reports_example/")

    # Generate text report
    print("\nGenerating Text Report...")
    text = generate_text_report(sample_result)
    print(text[:500])  # Print first part
    print(f"  ... (full report has {len(text)} characters)")

    # Generate all formats
    print("\nGenerating all report formats...")
    reports = generate_all_reports(sample_result, report_dir)
    print(f"  Generated reports:")
    for fmt, path in reports.items():
        print(f"    - {fmt}: {path}")


# Example 4: DeepTeam Vulnerability Definitions
def example_vulnerability_definitions() -> None:
    """Show DeepTeam vulnerability mappings."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: DeepTeam Vulnerability Definitions")
    print("=" * 80)

from .deepteam_generator import DEEPTEAM_VULNERABILITIES

    print("\nSupported Vulnerabilities (OWASP LLM Top 10 mapped):\n")
    for vuln_type, info in sorted(DEEPTEAM_VULNERABILITIES.items()):
        print(
            f"  {vuln_type:<30} {info['owasp']:<8} {info['description']}"
        )


# Example 5: MCP Security Testing
def example_mcp_security_testing() -> None:
    """Run MCP security tests."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: MCP Security Testing")
    print("=" * 80)

    print("\nMCP Security Test Suite covers:")
    tests = [
        "Tool authorization and access control",
        "Argument injection prevention",
        "Tool sequence integrity",
        "Error response leakage prevention",
        "Type validation enforcement",
        "Resource limits and boundaries",
        "Null/nil value handling",
        "Tool isolation",
        "Indirect injection via tool results",
    ]

    for i, test in enumerate(tests, 1):
        print(f"  {i}. {test}")

    print("\nRun MCP security tests with:")
    print("  pytest tests/model_free/test_mcp_security.py -v")


def main() -> None:
    """Run all examples."""
    import argparse

    parser = argparse.ArgumentParser(description="Red-Team Evaluation Examples")
    parser.add_argument(
        "--backend",
        choices=["local", "copilot"],
        default="local",
        help="Backend to use",
    )
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run specific example (1-5, default: all)",
    )

    args = parser.parse_args()

    # Initialize backend if requested
    backend = None
    if args.backend != "local":
        print(f"\nInitializing {args.backend} backend...")
        if args.backend == "copilot":
            from evals.deepeval.copilot_backend import CopilotBackend

            backend = CopilotBackend(model="gpt-5")

    examples = {
        1: example_deepteam_generation,
        2: lambda: example_multiturn_attacks(backend),
        3: example_reporting,
        4: example_vulnerability_definitions,
        5: example_mcp_security_testing,
    }

    if args.example:
        examples[args.example]()
    else:
        for example_func in examples.values():
            example_func()

    print("\n" + "=" * 80)
    print("Examples Complete!")
    print("=" * 80)
    print("\nFor more details, see:")
    print("  - evals/deepeval/RED_TEAM.md (comprehensive guide)")
    print("  - docs/red_team_scan_comparison.md (red team concepts)")


if __name__ == "__main__":
    main()
