from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from gemini_music_api.db import SessionLocal
from gemini_music_api.services.projections import recompute_all_daily_projections

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evals" / "reports" / "projection_backfill.json"


def main() -> int:
    with SessionLocal() as db:
        result = recompute_all_daily_projections(db)
        db.commit()

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS",
        "days_recomputed": result.get("days_recomputed", 0),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
