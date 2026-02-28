from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fastapi.testclient import TestClient

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "ai_kirtan_quality_report.json"

REQUIRED_ARRANGEMENT = {"drone_level", "percussion", "call_response"}


def main() -> int:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        user = client.post("/v1/users", json={"display_name": "AI Kirtan Verifier"})
        user.raise_for_status()
        user_id = user.json()["id"]
        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "ai kirtan contract verification",
                "mantra_key": "maha_mantra_hare_krishna_hare_rama",
                "mood": "neutral",
                "target_duration_minutes": 8,
            },
        )
        session.raise_for_status()
        session_id = session.json()["id"]

        scenarios = [
            {"mood": "anxious", "heart_rate": 120, "noise_level_db": 52},
            {"mood": "neutral", "heart_rate": 88, "noise_level_db": 45},
            {"mood": "joyful", "heart_rate": 76, "noise_level_db": 40},
        ]

        checks: list[dict[str, object]] = []
        quality_scores: list[float] = []
        for idx, scenario in enumerate(scenarios):
            event = client.post(
                f"/v1/sessions/{session_id}/events",
                json={
                    "event_type": "voice_window",
                    "client_event_id": f"ai-kirtan-{idx}",
                    "payload": {
                        "cadence_bpm": 74,
                        "practice_seconds": 180,
                        "heart_rate": scenario["heart_rate"],
                        "noise_level_db": scenario["noise_level_db"],
                        "flow_score": 0.73,
                        "pronunciation_score": 0.76,
                    },
                },
            )
            event.raise_for_status()

            adaptation = client.post(
                f"/v1/sessions/{session_id}/adaptations",
                json={"explicit_mood": scenario["mood"]},
            )
            adaptation.raise_for_status()
            body = adaptation.json()
            adaptation_json = body.get("adaptation_json", {})
            arrangement = adaptation_json.get("arrangement", {})
            coach_actions = adaptation_json.get("coach_actions", [])
            reason = str(body.get("reason", ""))

            contract_ok = REQUIRED_ARRANGEMENT.issubset(arrangement.keys()) and isinstance(coach_actions, list)
            explainability_ok = len(reason.split()) >= 4
            coach_quality_ok = len(coach_actions) >= 1
            quality = (
                (0.4 if contract_ok else 0.0)
                + (0.3 if coach_quality_ok else 0.0)
                + (0.3 if explainability_ok else 0.0)
            )
            quality_scores.append(quality)
            checks.append(
                {
                    "scenario": scenario,
                    "contract_ok": contract_ok,
                    "coach_quality_ok": coach_quality_ok,
                    "explainability_ok": explainability_ok,
                    "quality_score_0_to_1": round(quality, 3),
                }
            )

    mean_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    contract_pass_rate = sum(1 for check in checks if check["contract_ok"]) / len(checks) if checks else 0.0
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "contract": {
            "required_arrangement_fields": sorted(REQUIRED_ARRANGEMENT),
            "required_coach_actions_min": 1,
        },
        "checks": checks,
        "summary": {
            "contract_pass_rate": round(contract_pass_rate, 3),
            "quality_score_mean_0_to_1": round(mean_quality, 3),
        },
        "status": "PASS" if contract_pass_rate == 1.0 and mean_quality >= 0.85 else "FAIL",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
