from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
GOAL_REPORT = ROOT / "evals" / "reports" / "project_goal_status.json"
OUT_PATH = ROOT / "evals" / "reports" / "data_quality_checks.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _check(name: str, passed: bool, evidence: object) -> dict:
    return {"name": name, "passed": bool(passed), "evidence": evidence}


def main() -> int:
    scorecard = _load(SCORECARD_REPORT)
    goal = _load(GOAL_REPORT)

    automated = scorecard.get("automated_indicators", {})
    always_failures = scorecard.get("summary", {}).get("always_failures", [])

    instructional = goal.get("instructional_design", {})
    quality_gates = instructional.get("data_engineering_requirements", {}).get("quality_gates", [])

    checks = [
        _check(
            "idempotent_event_ingestion",
            float(automated.get("idempotent_event_ingestion", 0.0)) >= 1.0,
            automated.get("idempotent_event_ingestion", 0.0),
        ),
        _check(
            "no_always_case_failures",
            len(always_failures) == 0,
            always_failures,
        ),
        _check(
            "instructional_quality_gates",
            all(bool(item.get("passed", False)) for item in quality_gates),
            quality_gates,
        ),
        _check(
            "goal_on_track",
            bool(goal.get("summary", {}).get("on_track_for_hackathon_demo", False)),
            goal.get("summary", {}),
        ),
    ]

    passed = all(c["passed"] for c in checks)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
