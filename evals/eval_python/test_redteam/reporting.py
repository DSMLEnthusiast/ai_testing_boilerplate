"""Red-team evaluation reporting and visualization.

Generates comprehensive reports, statistics, and visualizations of red-team results.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


def generate_text_report(suite_result: dict[str, Any], output_path: Path | None = None) -> str:
    """Generate a text-based report of red-team results.

    Args:
        suite_result: Results from run_redteam_suite()
        output_path: Optional path to write report

    Returns:
        Formatted text report.
    """
    lines = [
        "=" * 80,
        "RED-TEAM EVALUATION REPORT",
        "=" * 80,
        "",
        f"Framework: {suite_result.get('framework', 'Unknown')}",
        f"Framework Version: {suite_result.get('framework_version', 'Unknown')}",
        "",
        "OVERALL STATISTICS",
        "-" * 80,
        f"Total Attack Runs: {suite_result.get('total_runs', 0)}",
        f"Scenarios Tested: {suite_result.get('scenarios_tested', 0)}",
        f"Repetitions: {suite_result.get('repetitions', 1)}",
        "",
    ]

    # Summary metrics
    summary = suite_result.get("summary", {})
    lines.extend([
        "VULNERABILITY METRICS",
        "-" * 80,
        f"Total Vulnerabilities Found: {summary.get('total_vulnerabilities_found', 0)}",
        f"Total Defended: {summary.get('total_defended', 0)}",
        f"Overall Vulnerability Rate: {summary.get('overall_vulnerability_rate', 0):.1%}",
        f"Overall Defense Rate: {summary.get('overall_defense_rate', 0):.1%}",
        "",
    ])

    # Per-attack-type breakdown
    by_attack_type = suite_result.get("by_attack_type", {})
    if by_attack_type:
        lines.extend([
            "VULNERABILITY BREAKDOWN BY ATTACK TYPE",
            "-" * 80,
        ])

        for attack_type in sorted(by_attack_type.keys()):
            agg = by_attack_type[attack_type]
            lines.extend([
                f"\n{attack_type.upper()}",
                f"  Attack Count: {agg.get('attack_count', 0)}",
                f"  Vulnerabilities Found: {agg.get('vulnerabilities_found', 0)}",
                f"  Defended: {agg.get('defended', 0)}",
                f"  Vulnerability Rate: {agg.get('vulnerability_rate', 0):.1%}",
                f"  Defense Rate: {agg.get('defense_rate', 0):.1%}",
                f"  Avg Latency: {agg.get('avg_latency_ms', 0):.1f}ms",
            ])

    lines.extend([
        "",
        "=" * 80,
    ])

    report = "\n".join(lines)

    if output_path:
        output_path.write_text(report, encoding="utf-8")

    return report


def generate_json_report(
    suite_result: dict[str, Any], output_path: Path | None = None
) -> str:
    """Generate a JSON-formatted report (same as input, optionally saved).

    Args:
        suite_result: Results from run_redteam_suite()
        output_path: Optional path to write JSON

    Returns:
        JSON string.
    """
    json_str = json.dumps(suite_result, indent=2)

    if output_path:
        output_path.write_text(json_str, encoding="utf-8")

    return json_str


def generate_html_report(
    suite_result: dict[str, Any], output_path: Path | None = None
) -> str:
    """Generate an HTML report with visualizations.

    Args:
        suite_result: Results from run_redteam_suite()
        output_path: Optional path to write HTML

    Returns:
        HTML string.
    """
    summary = suite_result.get("summary", {})
    by_attack_type = suite_result.get("by_attack_type", {})

    # Build attack type rows for table
    attack_rows = ""
    for attack_type in sorted(by_attack_type.keys()):
        agg = by_attack_type[attack_type]
        escaped_attack_type = escape(str(attack_type))
        vulnerability_rate = agg.get("vulnerability_rate", 0)
        defense_rate = agg.get("defense_rate", 0)

        # Color coding
        vuln_color = "red" if vulnerability_rate > 0.5 else "orange" if vulnerability_rate > 0.25 else "green"
        defense_color = "green" if defense_rate > 0.75 else "orange" if defense_rate > 0.5 else "red"

        attack_rows += f"""
        <tr>
            <td>{escaped_attack_type}</td>
            <td>{agg.get('attack_count', 0)}</td>
            <td>{agg.get('vulnerabilities_found', 0)}</td>
            <td><span style="color: {vuln_color}">{vulnerability_rate:.1%}</span></td>
            <td><span style="color: {defense_color}">{defense_rate:.1%}</span></td>
            <td>{agg.get('avg_latency_ms', 0):.1f}ms</td>
        </tr>
        """

    # Overall metrics color
    overall_vuln_rate = summary.get("overall_vulnerability_rate", 0)
    overall_color = "red" if overall_vuln_rate > 0.5 else "orange" if overall_vuln_rate > 0.25 else "green"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Red-Team Evaluation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1, h2 {{ color: #333; }}
        .summary {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: {overall_color}; }}
        table {{ border-collapse: collapse; width: 100%; background: white; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background-color: #333; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>🔴 Red-Team Evaluation Report</h1>

    <div class="summary">
        <h2>Overall Statistics</h2>
        <div class="metric">
            <span>Total Attacks:</span>
            <div class="metric-value">{suite_result.get('total_runs', 0)}</div>
        </div>
        <div class="metric">
            <span>Vulnerabilities Found:</span>
            <div class="metric-value">{summary.get('total_vulnerabilities_found', 0)}</div>
        </div>
        <div class="metric">
            <span>Defense Rate:</span>
            <div class="metric-value">{summary.get('overall_defense_rate', 0):.1%}</div>
        </div>
        <div class="metric">
            <span>Vulnerability Rate:</span>
            <div class="metric-value" style="color: {overall_color}">{overall_vuln_rate:.1%}</div>
        </div>
    </div>

    <div class="summary">
        <h2>Attack Type Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Attack Type</th>
                    <th>Count</th>
                    <th>Vulnerabilities</th>
                    <th>Vulnerability Rate</th>
                    <th>Defense Rate</th>
                    <th>Avg Latency</th>
                </tr>
            </thead>
            <tbody>
                {attack_rows}
            </tbody>
        </table>
    </div>

    <footer style="text-align: center; margin-top: 40px; color: #666; font-size: 12px;">
        Framework: {escape(str(suite_result.get('framework', 'Unknown')))} v{escape(str(suite_result.get('framework_version', 'Unknown')))}
    </footer>
</body>
</html>
"""

    if output_path:
        output_path.write_text(html, encoding="utf-8")

    return html


def generate_csv_report(
    suite_result: dict[str, Any], output_path: Path | None = None
) -> str:
    """Generate a CSV report for spreadsheet analysis.

    Args:
        suite_result: Results from run_redteam_suite()
        output_path: Optional path to write CSV

    Returns:
        CSV string.
    """
    lines = [
        "Attack Type,Attack Count,Vulnerabilities Found,Defended,Vulnerability Rate,Defense Rate,Avg Latency (ms)",
    ]

    by_attack_type = suite_result.get("by_attack_type", {})
    for attack_type in sorted(by_attack_type.keys()):
        agg = by_attack_type[attack_type]
        lines.append(
            f"{attack_type},"
            f"{agg.get('attack_count', 0)},"
            f"{agg.get('vulnerabilities_found', 0)},"
            f"{agg.get('defended', 0)},"
            f"{agg.get('vulnerability_rate', 0)},"
            f"{agg.get('defense_rate', 0)},"
            f"{agg.get('avg_latency_ms', 0):.1f}"
        )

    csv = "\n".join(lines)

    if output_path:
        output_path.write_text(csv, encoding="utf-8")

    return csv


def generate_all_reports(
    suite_result: dict[str, Any], output_dir: Path
) -> dict[str, Path]:
    """Generate all report formats to a directory.

    Args:
        suite_result: Results from run_redteam_suite()
        output_dir: Directory to write reports

    Returns:
        Dict mapping format names to output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "text": output_dir / "report.txt",
        "json": output_dir / "report.json",
        "html": output_dir / "report.html",
        "csv": output_dir / "report.csv",
    }

    generate_text_report(suite_result, paths["text"])
    generate_json_report(suite_result, paths["json"])
    generate_html_report(suite_result, paths["html"])
    generate_csv_report(suite_result, paths["csv"])

    return paths
