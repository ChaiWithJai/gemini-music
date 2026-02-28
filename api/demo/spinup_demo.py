from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/gemini_music_demo.db")

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app


def run_demo() -> dict:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        user = client.post("/v1/users", json={"display_name": "Hackathon Demo User"}).json()
        user_id = user["id"]

        client.put(
            f"/v1/users/{user_id}/consent",
            json={
                "biometric_enabled": True,
                "environmental_enabled": True,
                "raw_audio_storage_enabled": False,
                "policy_version": "v1",
            },
        )

        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "Live Maha Mantra kirtan demo",
                "mantra_key": "maha_mantra_hare_krishna_hare_rama",
                "mood": "grounded",
                "target_duration_minutes": 10,
            },
        ).json()
        session_id = session["id"]

        for i, cadence in enumerate([72, 73, 72, 74]):
            client.post(
                f"/v1/sessions/{session_id}/events",
                json={
                    "event_type": "voice_window",
                    "client_event_id": f"demo-evt-{i}",
                    "payload": {
                        "cadence_bpm": cadence,
                        "pronunciation_score": 0.9,
                        "flow_score": 0.88,
                        "practice_seconds": 180,
                        "heart_rate": 92,
                        "adaptation_helpful": True,
                    },
                },
            )

        adaptation = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "grounded"},
        ).json()

        end = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 5, "completed_goal": True},
        ).json()

        lineages = ["sadhguru", "shree_vallabhacharya", "vaishnavism"]
        bhav_results = {}
        for lineage in lineages:
            bhav = client.post(
                f"/v1/sessions/{session_id}/bhav",
                json={
                    "golden_profile": "maha_mantra_v1",
                    "lineage": lineage,
                    "persist": False,
                },
            ).json()
            bhav_results[lineage] = {
                "discipline": bhav["discipline"],
                "resonance": bhav["resonance"],
                "coherence": bhav["coherence"],
                "composite": bhav["composite"],
                "passes_golden": bhav["passes_golden"],
            }

        return {
            "user_id": user_id,
            "session_id": session_id,
            "adaptation": {
                "tempo_bpm": adaptation["tempo_bpm"],
                "guidance_intensity": adaptation["guidance_intensity"],
                "key_center": adaptation["key_center"],
            },
            "session_summary": end["summary"],
            "bhav_by_lineage": bhav_results,
        }


if __name__ == "__main__":
    result = run_demo()
    out_path = Path("demo/latest_demo_output.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nWrote demo artifact: {out_path}")
