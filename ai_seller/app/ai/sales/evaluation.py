"""Evaluation dataset loader and a lightweight regression runner.

The dataset lives in rag/evaluation/sales_rag_eval.jsonl. Each case describes an
expected intent and required behavior; full behavior checks need an LLM, so the
runner accepts a classify callback and an optional behavior checker.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.ai.sales.taxonomy import is_valid_intent

_DATA_DIR = Path(__file__).resolve().parents[3] / "rag"


def eval_path() -> Path:
    env_path = os.environ.get("SALES_RAG_EVAL_PATH")
    if env_path:
        return Path(env_path)
    return _DATA_DIR / "evaluation" / "sales_rag_eval.jsonl"


@dataclass
class EvalCase:
    """A single regression case."""

    id: str
    category: str
    input: str
    expected_intent: str
    must: str
    context: Dict[str, Any] = field(default_factory=dict)
    required_behavior: List[str] = field(default_factory=list)
    forbidden_behaviors: List[str] = field(default_factory=list)
    pass_rule: str = ""

    @property
    def intent_valid(self) -> bool:
        return is_valid_intent(self.expected_intent)


def load_cases(path: Optional[Path] = None) -> List[EvalCase]:
    target = path or eval_path()
    if not target.exists():
        return []
    cases: List[EvalCase] = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            expected = obj.get("expected", {})
            cases.append(
                EvalCase(
                    id=obj.get("id", ""),
                    category=obj.get("category", ""),
                    input=obj.get("input", ""),
                    context=obj.get("context") or {},
                    expected_intent=expected.get("intent", ""),
                    must=expected.get("must", ""),
                    required_behavior=list(expected.get("required_behavior") or []),
                    forbidden_behaviors=list(obj.get("forbidden_behaviors") or []),
                    pass_rule=obj.get("pass_rule", ""),
                )
            )
    return cases


def validate_cases(cases: List[EvalCase]) -> List[EvalCase]:
    """Return cases whose expected intent is not in the taxonomy."""
    return [case for case in cases if not case.intent_valid]


def run_eval(
    cases: List[EvalCase],
    classify: Callable[[EvalCase], Optional[str]],
    behavior_check: Optional[Callable[[EvalCase, str], bool]] = None,
) -> Dict[str, Any]:
    """Run regression checks.

    A case passes when the predicted intent matches the expected intent and (when a
    behavior_check is provided) the required behavior is considered present.
    """
    results: List[Dict[str, Any]] = []
    passed = 0
    for case in cases:
        predicted = classify(case)
        intent_ok = bool(predicted) and str(predicted).upper() == case.expected_intent.upper()
        behavior_ok = behavior_check(case, predicted or "") if behavior_check else True
        ok = intent_ok and behavior_ok
        passed += int(ok)
        results.append(
            {
                "id": case.id,
                "category": case.category,
                "expected_intent": case.expected_intent,
                "predicted_intent": predicted,
                "intent_ok": intent_ok,
                "behavior_ok": behavior_ok,
                "passed": ok,
            }
        )
    total = len(cases)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "results": results,
    }
