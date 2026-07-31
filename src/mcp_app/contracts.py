from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NormalizedRun:
    run_id: str
    scenario_id: str
    schema_version: str = "1.0"
    agent_runtime: str = "model-free"
    model_provider: str = "deterministic"
    seed: int | None = None
    repetition_index: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    response: str = ""
    trace_status: str = "complete"
    failure_category: str | None = None
    latency_ms: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JudgeVerdict:
    passed: bool
    score: float
    reason: str
    rubric_id: str = ""
    judge_model: str = ""
    judge_provider: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "JudgeVerdict":
        return cls(bool(payload["passed"]), float(payload["score"]), str(payload["reason"]), str(payload.get("rubric_id", "")), str(payload.get("judge_model", "")), str(payload.get("judge_provider", "")))
