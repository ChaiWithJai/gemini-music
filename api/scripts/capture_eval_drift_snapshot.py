from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from gemini_music_api.db import SessionLocal
from gemini_music_api.models import EvalDriftSnapshot

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
BASELINE_PATH = ROOT / "evals" / "reports" / "eval_baseline.json"
OUT_PATH = ROOT / "evals" / "reports" / "eval_drift_snapshot.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rigor_score(scorecard: dict) -> float:
    for dim in scorecard.get("scorecard", {}).get("dimensions", []):
        if dim.get("id") == "G_scientific_eval_rigor":
            return float(dim.get("weighted_score", 0.0))
    return 0.0


def main() -> int:
    current = _load(SCORECARD_REPORT)
    if not current:
        raise RuntimeError(f"Missing scorecard report at {SCORECARD_REPORT}")

    current_total = float(current.get("scorecard", {}).get("total_score_0_to_100", 0.0))
    current_rigor = _rigor_score(current)

    baseline = _load(BASELINE_PATH)
    if not baseline:
        baseline = {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "total_score_0_to_100": current_total,
            "rigor_score": current_rigor,
        }
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    baseline_total = float(baseline.get("total_score_0_to_100", current_total))
    baseline_rigor = float(baseline.get("rigor_score", current_rigor))

    total_delta = round(current_total - baseline_total, 3)
    rigor_delta = round(current_rigor - baseline_rigor, 3)

    attempts = int(current.get("summary", {}).get("total_attempts", 0) or 0)
    pass_rate = float(current.get("summary", {}).get("attempt_pass_rate", 0.0) or 0.0)
    if attempts > 0:
        se = math.sqrt(max(0.0, pass_rate * (1.0 - pass_rate) / attempts))
    else:
        se = 0.0
    ci95_low = round(max(0.0, pass_rate - (1.96 * se)), 4)
    ci95_high = round(min(1.0, pass_rate + (1.96 * se)), 4)

    status = "PASS"
    if total_delta < -2.0 or rigor_delta < -0.3:
        status = "FAIL"

    snapshot = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "baseline": {
            "total_score_0_to_100": baseline_total,
            "rigor_score": baseline_rigor,
        },
        "current": {
            "total_score_0_to_100": current_total,
            "rigor_score": current_rigor,
            "attempt_pass_rate": pass_rate,
        },
        "deltas": {
            "total_score_delta": total_delta,
            "rigor_score_delta": rigor_delta,
        },
        "confidence": {
            "attempt_count": attempts,
            "ci95_low": ci95_low,
            "ci95_high": ci95_high,
        },
    }

    with SessionLocal() as db:
        row = EvalDriftSnapshot(
            baseline_name="default",
            total_score=current_total,
            rigor_score=current_rigor,
            total_score_delta=total_delta,
            rigor_score_delta=rigor_delta,
            attempt_pass_rate_mean=pass_rate,
            attempt_pass_rate_std=0.0,
            ci95_low=ci95_low,
            ci95_high=ci95_high,
            status=status,
            detail_json=snapshot,
        )
        db.add(row)
        db.commit()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
