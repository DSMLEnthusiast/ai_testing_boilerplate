"""DeepTeam attack scenario generator for dynamic red-team testing.

This module generates adversarial attacks using DeepTeam's attack simulator,
replacing static hand-written scenarios with dynamic, vulnerability-specific attacks.
"""

from __future__ import annotations

from typing import Any


DEEPTEAM_VULNERABILITIES = {
    "prompt_injection": {
        "description": "Direct system override and instruction confusion",
        "owasp": "LLM01",
        "deepteam_class": "Robustness",
    },
    "jailbreak": {
        "description": "DAN, roleplay, hypothetical, and other safety bypasses",
        "owasp": "LLM01",
        "deepteam_class": "Robustness",
    },
    "pii_leakage": {
        "description": "Personal data extraction and memorization",
        "owasp": "LLM02",
        "deepteam_class": "PIILeakage",
    },
    "system_prompt_extraction": {
        "description": "Disclosure of system and hidden instructions",
        "owasp": "LLM07",
        "deepteam_class": "PromptLeakage",
    },
    "indirect_injection": {
        "description": "Malicious instructions via documents or tools",
        "owasp": "LLM01",
        "deepteam_class": "IndirectInstruction",
    },
    "excessive_agency": {
        "description": "Authority escalation and unsanctioned decisions",
        "owasp": "LLM06",
        "deepteam_class": "ExcessiveAgency",
    },
    "insecure_output": {
        "description": "XSS, SQL, command, and other injection-shaped output",
        "owasp": "LLM05",
        "deepteam_class": "InsecureOutput",
    },
    "encoding_evasion": {
        "description": "Base64, ROT13, hex, and other encoding obfuscation",
        "owasp": "LLM01",
        "deepteam_class": "EncodingEvasion",
    },
    "data_poisoning": {
        "description": "False facts and backdoor priming",
        "owasp": "LLM04",
        "deepteam_class": "DataPoisoning",
    },
    "misinformation": {
        "description": "Fabrication, unsupported claims, overconfident falsehoods",
        "owasp": "LLM09",
        "deepteam_class": "Misinformation",
    },
}


def generate_attacks_with_deepteam(
    vulnerabilities: list[str] | None = None,
    target_description: str = "Math MCP agent with tool calling capability",
    num_attacks_per_type: int = 3,
    tools_context: str | None = None,
) -> list[dict[str, Any]]:
    """Generate adversarial attacks using DeepTeam's attack simulator.

    Args:
        vulnerabilities: List of vulnerability types to generate (None = all)
        target_description: Description of the target application
        num_attacks_per_type: Number of attack variations per vulnerability
        tools_context: Available tools and their signatures (enables tool-aware attacks)

    Returns:
        List of attack scenarios with generated adversarial prompts.

    Raises:
        ImportError: If deepteam is not installed.
    """
    try:
        from deepteam.attacks.attack_simulator import AttackSimulator
        from deepteam.vulnerabilities import (
            ExcessiveAgency,
            IndirectInstruction,
            PromptLeakage,
            Robustness,
        )
    except ImportError as error:
        raise ImportError("deepteam not installed. Install with: pip install deepteam") from error

    if vulnerabilities is None:
        vulnerabilities = list(DEEPTEAM_VULNERABILITIES.keys())

    # Filter to supported vulnerabilities
    vulnerabilities = [
        v for v in vulnerabilities if v in DEEPTEAM_VULNERABILITIES
    ]

    # Enhance target description with tool context for more targeted attacks
    enhanced_description = target_description
    if tools_context:
        enhanced_description = f"{target_description}\n\n{tools_context}"

    from ..copilot_llm import CopilotLLMJudge

    vulnerability_classes = {
        "ExcessiveAgency": ExcessiveAgency,
        "IndirectInstruction": IndirectInstruction,
        "PromptLeakage": PromptLeakage,
        "Robustness": Robustness,
    }
    simulator_model = CopilotLLMJudge()
    deepteam_vulnerabilities = []
    attack_type_by_vulnerability_type: dict[str, str] = {}

    for vulnerability_name in vulnerabilities:
        config = DEEPTEAM_VULNERABILITIES[vulnerability_name]
        vulnerability_class = vulnerability_classes.get(config["deepteam_class"])
        if vulnerability_class is None:
            print(
                f"Warning: DeepTeam 1.0.7 has no supported class for "
                f"{vulnerability_name}; skipping"
            )
            continue

        # Keep generated attacks focused on the threat relevant to this target.
        type_by_class = {
            "Robustness": ["hijacking"],
            "ExcessiveAgency": ["permissions"],
            "IndirectInstruction": ["tool_output_injection"],
            "PromptLeakage": ["instructions"],
        }
        vulnerability_types = type_by_class.get(config["deepteam_class"])
        kwargs: dict[str, Any] = {
            "async_mode": False,
            "purpose": enhanced_description,
            "simulator_model": simulator_model,
        }
        if vulnerability_types:
            kwargs["types"] = vulnerability_types

        deepteam_vulnerabilities.append(vulnerability_class(**kwargs))
        for vulnerability_type in vulnerability_types or []:
            attack_type_by_vulnerability_type[vulnerability_type] = vulnerability_name

    if not deepteam_vulnerabilities:
        return []

    from deepteam.attacks.attack_simulator import AttackSimulator

    simulator = AttackSimulator(
        purpose=enhanced_description,
        max_concurrent=1,
        simulator_model=simulator_model,
    )
    test_cases = simulator.simulate(
        attacks_per_vulnerability_type=num_attacks_per_type,
        vulnerabilities=deepteam_vulnerabilities,
        ignore_errors=True,
        simulator_model=simulator_model,
    )

    attacks = []
    for index, test_case in enumerate(test_cases):
        prompt = getattr(test_case, "input", None)
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        vulnerability_type = getattr(test_case, "vulnerability_type", "unknown")
        vulnerability_type_name = getattr(
            vulnerability_type, "value", str(vulnerability_type)
        )
        attack_type = attack_type_by_vulnerability_type.get(
            vulnerability_type_name, "unknown"
        )
        config = DEEPTEAM_VULNERABILITIES.get(attack_type, {})
        attacks.append(
            {
                "id": f"deepteam-{attack_type}-{index}",
                "prompt": prompt,
                "attack_type": attack_type,
                "vulnerability_type": vulnerability_type_name,
                "owasp_category": config.get("owasp", "LLM01"),
                "description": config.get("description", "DeepTeam-generated attack"),
                "target_boundary": "agent",
                "rubric_id": "deepteam-v1",
                "expected_tools": [],
                "is_generated": True,
                "generator": "deepteam",
            }
        )

    return attacks
