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


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    scorecard = _load(SCORECARD_REPORT)
    goal = _load(GOAL_REPORT)

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
        }
        for row in rows
    ]

    summary = {
        "scorecard_total_0_to_100": scorecard.get("scorecard", {}).get("total_score_0_to_100", 0.0),
        "on_track_for_hackathon_demo": goal.get("summary", {}).get("on_track_for_hackathon_demo", False),
        "days_reported": len(kpi_rows),
    }

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "window": "last_7_rows",
        "summary": summary,
        "daily_kpis": kpi_rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
