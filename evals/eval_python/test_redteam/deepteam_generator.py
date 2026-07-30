"""DeepTeam attack scenario generator for dynamic red-team testing.

This module generates adversarial attacks using DeepTeam's RedTeamer,
replacing static hand-written scenarios with dynamic, vulnerability-specific attacks.
"""

from __future__ import annotations

from typing import Any


DEEPTEAM_VULNERABILITIES = {
    "prompt_injection": {
        "description": "Direct system override and instruction confusion",
        "owasp": "LLM01",
        "deepteam_type": "PromptInjection",
    },
    "jailbreak": {
        "description": "DAN, roleplay, hypothetical, and other safety bypasses",
        "owasp": "LLM01",
        "deepteam_type": "Jailbreak",
    },
    "pii_leakage": {
        "description": "Personal data extraction and memorization",
        "owasp": "LLM02",
        "deepteam_type": "PIILeakage",
    },
    "system_prompt_extraction": {
        "description": "Disclosure of system and hidden instructions",
        "owasp": "LLM07",
        "deepteam_type": "SystemPromptExtraction",
    },
    "indirect_injection": {
        "description": "Malicious instructions via documents or tools",
        "owasp": "LLM01",
        "deepteam_type": "IndirectInjection",
    },
    "excessive_agency": {
        "description": "Authority escalation and unsanctioned decisions",
        "owasp": "LLM06",
        "deepteam_type": "ExcessiveAgency",
    },
    "insecure_output": {
        "description": "XSS, SQL, command, and other injection-shaped output",
        "owasp": "LLM05",
        "deepteam_type": "InsecureOutput",
    },
    "encoding_evasion": {
        "description": "Base64, ROT13, hex, and other encoding obfuscation",
        "owasp": "LLM01",
        "deepteam_type": "EncodingEvasion",
    },
    "data_poisoning": {
        "description": "False facts and backdoor priming",
        "owasp": "LLM04",
        "deepteam_type": "DataPoisoning",
    },
    "misinformation": {
        "description": "Fabrication, unsupported claims, overconfident falsehoods",
        "owasp": "LLM09",
        "deepteam_type": "Misinformation",
    },
}


def generate_attacks_with_deepteam(
    vulnerabilities: list[str] | None = None,
    target_description: str = "Math MCP agent with tool calling capability",
    num_attacks_per_type: int = 3,
    tools_context: str | None = None,
) -> list[dict[str, Any]]:
    """Generate adversarial attacks using DeepTeam's RedTeamer.

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
        from deepteam import RedTeamer
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

    red_teamer = RedTeamer(target=enhanced_description)
    attacks = []

    for vuln in vulnerabilities:
        vuln_config = DEEPTEAM_VULNERABILITIES[vuln]
        vuln_type = vuln_config["deepteam_type"]

        for i in range(num_attacks_per_type):
            try:
                # Generate attack using DeepTeam
                attack = red_teamer.generate_attack(
                    vulnerability_type=vuln_type,
                    attack_index=i,
                )

                attacks.append(
                    {
                        "id": f"deepteam-{vuln}-{i}",
                        "prompt": attack.attack_prompt,
                        "attack_type": vuln,
                        "vulnerability_type": vuln_type,
                        "owasp_category": vuln_config["owasp"],
                        "description": vuln_config["description"],
                        "target_boundary": "agent",
                        "rubric_id": "deepteam-v1",
                        "expected_tools": [],  # Will be determined by agent
                        "is_generated": True,
                        "generator": "deepteam",
                    }
                )
            except Exception as e:
                # Skip attacks that fail to generate
                print(f"Warning: Failed to generate {vuln_type} attack #{i}: {e}")
                continue

    return attacks
