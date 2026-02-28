from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fastapi.testclient import TestClient

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "chaos_reliability_report.json"


def _create_user(client: TestClient, name: str) -> str:
    resp = client.post("/v1/users", json={"display_name": name})
    resp.raise_for_status()
    return resp.json()["id"]


def _start_session(client: TestClient, user_id: str, mood: str) -> str:
    resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "chaos reliability scenario",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": mood,
            "target_duration_minutes": 6,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def main() -> int:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scenarios": {},
        "status": "PASS",
    }

    with TestClient(app) as client:
        user_id = _create_user(client, "Chaos Runner")

        # no-biometrics
        s1 = _start_session(client, user_id, "neutral")
        client.post(
            f"/v1/sessions/{s1}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "chaos-no-bio",
                "payload": {"cadence_bpm": 73, "practice_seconds": 180},
            },
        ).raise_for_status()
        r1 = client.post(f"/v1/sessions/{s1}/adaptations", json={"explicit_mood": "neutral"})
        no_bio_ok = r1.status_code == 200
        report["scenarios"]["no_biometrics"] = {
            "passed": no_bio_ok,
            "guidance_intensity": r1.json().get("guidance_intensity") if no_bio_ok else None,
        }

        # noisy audio
        s2 = _start_session(client, user_id, "neutral")
        client.post(
            f"/v1/sessions/{s2}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "chaos-noisy",
                "payload": {"cadence_bpm": 78, "practice_seconds": 180, "noise_level_db": 86},
            },
        ).raise_for_status()
        r2 = client.post(f"/v1/sessions/{s2}/adaptations", json={"explicit_mood": "neutral"})
        noisy_ok = r2.status_code == 200 and r2.json().get("guidance_intensity") == "high"
        report["scenarios"]["high_noise"] = {
            "passed": noisy_ok,
            "guidance_intensity": r2.json().get("guidance_intensity") if r2.status_code == 200 else None,
        }

        # transient fallback
        import gemini_music_api.main as main_module

        original_try = main_module.try_gemini_adaptation

        def _raise_transient(*_: object, **__: object) -> dict[str, object] | None:
            raise RuntimeError("simulated_transient_upstream_error")

        s3 = _start_session(client, user_id, "anxious")
        client.post(
            f"/v1/sessions/{s3}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "chaos-transient",
                "payload": {"cadence_bpm": 82, "practice_seconds": 200, "heart_rate": 118},
            },
        ).raise_for_status()

        main_module.try_gemini_adaptation = _raise_transient
        try:
            r3 = client.post(f"/v1/sessions/{s3}/adaptations", json={"explicit_mood": "anxious"})
        finally:
            main_module.try_gemini_adaptation = original_try

        transient_ok = r3.status_code == 200
        report["scenarios"]["transient_failure_fallback"] = {
            "passed": transient_ok,
            "fallback_reason": (
                r3.json().get("adaptation_json", {}).get("fallback", {}).get("reason")
                if transient_ok
                else None
            ),
        }

        continuity_ok = True
        for idx, sid in enumerate([s1, s2, s3], start=1):
            end = client.post(f"/v1/sessions/{sid}/end", json={"user_value_rating": 4.4, "completed_goal": True})
            passed = end.status_code == 200
            report["scenarios"][f"session_continuity_{idx}"] = {"passed": passed}
            continuity_ok = continuity_ok and passed

    all_passed = all(bool(item.get("passed")) for item in report["scenarios"].values())
    report["status"] = "PASS" if all_passed and continuity_ok else "FAIL"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
