from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
GOAL_REPORT = ROOT / "evals" / "reports" / "project_goal_status.json"
DRIFT_REPORT = ROOT / "evals" / "reports" / "eval_drift_snapshot.json"
OUT_PATH = ROOT / "evals" / "reports" / "release_gate_status.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _dim_score(scorecard: dict, dim_id: str) -> float:
    dims = scorecard.get("scorecard", {}).get("dimensions", [])
    for dim in dims:
        if dim.get("id") == dim_id:
            return float(dim.get("weighted_score", 0.0))
    return 0.0


def main() -> int:
    scorecard = _load(SCORECARD_REPORT)
    goal = _load(GOAL_REPORT)
    drift = _load(DRIFT_REPORT)

    min_total = float(os.getenv("RELEASE_MIN_SCORECARD_TOTAL", "85"))
    min_demis = float(os.getenv("RELEASE_MIN_DEMIS", "40"))
    min_sundar = float(os.getenv("RELEASE_MIN_SUNDAR", "40"))

    min_eco = float(os.getenv("RELEASE_MIN_ECOSYSTEM_SCORE", "10"))
    min_business = float(os.getenv("RELEASE_MIN_BUSINESS_SCORE", "9"))
    min_rigor = float(os.getenv("RELEASE_MIN_RIGOR_SCORE", "9.6"))

    total = float(scorecard.get("scorecard", {}).get("total_score_0_to_100", 0.0))
    demis = float(scorecard.get("scorecard", {}).get("demis_lens_score_0_to_50", 0.0))
    sundar = float(scorecard.get("scorecard", {}).get("sundar_lens_score_0_to_50", 0.0))

    d_eco = _dim_score(scorecard, "D_ecosystem_leverage")
    f_business = _dim_score(scorecard, "F_measurable_business_signal")
    g_rigor = _dim_score(scorecard, "G_scientific_eval_rigor")

    checks = [
        {"name": "scorecard_total", "passed": total >= min_total, "value": total, "min": min_total},
        {"name": "demis_lens", "passed": demis >= min_demis, "value": demis, "min": min_demis},
        {"name": "sundar_lens", "passed": sundar >= min_sundar, "value": sundar, "min": min_sundar},
        {"name": "ecosystem_gap_closed", "passed": d_eco >= min_eco, "value": d_eco, "min": min_eco},
        {"name": "business_gap_closed", "passed": f_business >= min_business, "value": f_business, "min": min_business},
        {"name": "rigor_gap_closed", "passed": g_rigor >= min_rigor, "value": g_rigor, "min": min_rigor},
        {
            "name": "goal_on_track",
            "passed": bool(goal.get("summary", {}).get("on_track_for_hackathon_demo", False)),
            "value": goal.get("summary", {}).get("on_track_for_hackathon_demo", False),
            "min": True,
        },
        {
            "name": "drift_guard",
            "passed": drift.get("status") == "PASS",
            "value": drift.get("status"),
            "min": "PASS",
        },
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
