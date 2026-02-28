from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fastapi.testclient import TestClient

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "adapter_starter_kit_verification.json"


def main() -> int:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    checks: dict[str, bool] = {}
    with TestClient(app) as client:
        user = client.post("/v1/users", json={"display_name": "Adapter Verifier"})
        user.raise_for_status()
        user_id = user.json()["id"]
        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "adapter starter kit verification",
                "mantra_key": "om_namah_shivaya",
                "mood": "neutral",
                "target_duration_minutes": 6,
            },
        )
        session.raise_for_status()
        session_id = session.json()["id"]

        webhook = client.post(
            "/v1/integrations/webhooks",
            json={
                "target_url": "https://example.org/hook",
                "adapter_id": "content_playlist_adapter",
                "event_types": ["session_ended", "adaptation_applied"],
                "is_active": True,
            },
        )
        checks["webhook_subscription"] = webhook.status_code == 201

        wearable = client.post(
            "/v1/integrations/events",
            json={
                "session_id": session_id,
                "partner_source": "wearable_partner",
                "adapter_id": "wearable_hr_stream",
                "event_type": "partner_signal",
                "client_event_id": "adapter-wearable",
                "payload": {"signal_type": "heart_rate", "heart_rate": 109, "cadence_bpm": 74, "practice_seconds": 120},
            },
        )
        checks["wearable_adapter_ingest"] = wearable.status_code == 201

        content = client.post(
            "/v1/integrations/events",
            json={
                "session_id": session_id,
                "partner_source": "content_partner",
                "adapter_id": "content_playlist_sync",
                "event_type": "partner_signal",
                "client_event_id": "adapter-content",
                "payload": {"signal_type": "playlist_sync", "playlist_id": "starter_kit_set", "cadence_bpm": 72, "practice_seconds": 120},
            },
        )
        checks["content_adapter_ingest"] = content.status_code == 201

        adaptation = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "neutral"},
        )
        checks["adaptation_from_adapter_context"] = adaptation.status_code == 200

        end = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 4.6, "completed_goal": True},
        )
        checks["session_end"] = end.status_code == 200

        ecosystem = client.get("/v1/integrations/exports/ecosystem-usage/daily")
        checks["ecosystem_export"] = ecosystem.status_code == 200
        eco = ecosystem.json() if ecosystem.status_code == 200 else {}
        checks["wearable_usage_reflected"] = int(eco.get("wearable_adapter_events", 0)) >= 1
        checks["content_usage_reflected"] = int(eco.get("content_export_events", 0)) >= 1

    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "checks": checks,
        "status": status,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
