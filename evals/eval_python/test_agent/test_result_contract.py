from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mcp_app.contracts import NormalizedRun


RESULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "golden" / "result-schema-v1.json"


def test_normalized_run_matches_versioned_result_schema() -> None:
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    result = NormalizedRun(run_id="offline-1", scenario_id="add-basic").to_dict()
    Draft202012Validator(schema).validate(result)
