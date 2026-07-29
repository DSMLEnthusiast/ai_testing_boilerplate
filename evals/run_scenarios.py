from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.model_free.scenario_runner import load_scenarios, run_scenario


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("results.json"))
    args = parser.parse_args()
    scenarios = load_scenarios(Path("evals/golden/scenarios.json"))
    results = [run_scenario(s, repetition_index=i) for i in range(args.repetitions) for s in scenarios]
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
