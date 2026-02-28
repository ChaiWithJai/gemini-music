from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import select

from gemini_music_api.db import SessionLocal
from gemini_music_api.models import BusinessSignalDaily

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
GOAL_REPORT = ROOT / "evals" / "reports" / "project_goal_status.json"
OUT_PATH = ROOT / "evals" / "reports" / "weekly_kpi_report.json"
NORTH_STAR_CONTRACT = ROOT.parent / "docs" / "contracts" / "north_star_metric.v1.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _north_star(row: dict) -> float:
    started = max(1, int(row.get("sessions_started", 0)))
    meaningful_rate = float(row.get("meaningful_sessions", 0)) / float(started)
    helpful = float(row.get("adaptation_helpful_rate", 0.0))
    bhav = float(row.get("bhav_pass_rate", 0.0))
    return round(max(0.0, min(1.0, meaningful_rate * helpful * bhav)), 4)


def _trend_delta(rows: list[dict], key: str) -> float:
    if len(rows) < 2:
        return 0.0
    return round(float(rows[-1].get(key, 0.0)) - float(rows[0].get(key, 0.0)), 4)


def main() -> int:
    scorecard = _load(SCORECARD_REPORT)
    goal = _load(GOAL_REPORT)
    north_star_contract = _load(NORTH_STAR_CONTRACT)

    with SessionLocal() as db:
        rows = db.scalars(
            select(BusinessSignalDaily).order_by(BusinessSignalDaily.date_key.desc()).limit(7)
        ).all()

    kpi_rows = [
        {
            "date_key": row.date_key,
            "sessions_started": row.sessions_started,
            "sessions_completed": row.sessions_completed,
            "meaningful_sessions": row.meaningful_sessions,
            "avg_user_value_rating": row.avg_user_value_rating,
            "adaptation_helpful_rate": row.adaptation_helpful_rate,
            "day7_returning_users": row.day7_returning_users,
            "unique_active_users": row.unique_active_users,
            "bhav_pass_rate": row.bhav_pass_rate,
            "north_star_value": _north_star(
                {
                    "sessions_started": row.sessions_started,
                    "meaningful_sessions": row.meaningful_sessions,
                    "adaptation_helpful_rate": row.adaptation_helpful_rate,
                    "bhav_pass_rate": row.bhav_pass_rate,
                }
            ),
        }
        for row in reversed(rows)
    ]

    attempt_ci = scorecard.get("summary", {}).get("attempt_pass_rate_ci95", {})
    confidence_note = (
        f"Eval attempt pass-rate CI95 low/high: {attempt_ci.get('low', 0.0)} / {attempt_ci.get('high', 0.0)}."
    )

    summary = {
        "scorecard_total_0_to_100": scorecard.get("scorecard", {}).get("total_score_0_to_100", 0.0),
        "on_track_for_hackathon_demo": goal.get("summary", {}).get("on_track_for_hackathon_demo", False),
        "days_reported": len(kpi_rows),
        "north_star_metric_version": north_star_contract.get("version", "unknown"),
        "north_star_metric_id": north_star_contract.get("metric_id", "unknown"),
        "confidence_note": confidence_note,
    }

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window": "last_7_rows",
        "summary": summary,
        "trend_deltas": {
            "sessions_started_delta": _trend_delta(kpi_rows, "sessions_started"),
            "sessions_completed_delta": _trend_delta(kpi_rows, "sessions_completed"),
            "meaningful_sessions_delta": _trend_delta(kpi_rows, "meaningful_sessions"),
            "adaptation_helpful_rate_delta": _trend_delta(kpi_rows, "adaptation_helpful_rate"),
            "day7_returning_users_delta": _trend_delta(kpi_rows, "day7_returning_users"),
            "north_star_delta": _trend_delta(kpi_rows, "north_star_value"),
        },
        "north_star_contract": north_star_contract,
        "daily_kpis": kpi_rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
