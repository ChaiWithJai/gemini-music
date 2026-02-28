from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evals" / "reports" / "maha_mantra_poc_status.json"


def _clamp01(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _run_scenario() -> dict[str, Any]:
    db_path = Path("/tmp/gemini_music_maha_poc.db")
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    from fastapi.testclient import TestClient

    from gemini_music_api.db import Base, engine
    from gemini_music_api.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        ui_resp = client.get("/poc/")
        ui_ok = ui_resp.status_code == 200 and "Maha Mantra Learning Studio" in ui_resp.text

        user = client.post("/v1/users", json={"display_name": "POC Singer"})
        assert user.status_code == 201, user.text
        user_id = user.json()["id"]

        consent = client.put(
            f"/v1/users/{user_id}/consent",
            json={
                "biometric_enabled": True,
                "environmental_enabled": True,
                "raw_audio_storage_enabled": False,
                "policy_version": "v1",
            },
        )
        assert consent.status_code == 200, consent.text

        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "Maha Mantra POC flow test",
                "mantra_key": "maha_mantra_hare_krishna_hare_rama",
                "mood": "focused",
                "target_duration_minutes": 3,
            },
        )
        assert session.status_code == 201, session.text
        session_id = session.json()["id"]

        stage_metrics = {
            "guided": {
                "duration_seconds": 45,
                "voice_ratio_total": 0.71,
                "voice_ratio_student": None,
                "voice_ratio_guru": None,
                "pitch_stability": 0.84,
                "cadence_bpm": 72,
                "cadence_consistency": 0.81,
                "avg_energy": 0.5,
            },
            "call_response": {
                "duration_seconds": 40,
                "voice_ratio_total": 0.55,
                "voice_ratio_student": 0.74,
                "voice_ratio_guru": 0.17,
                "pitch_stability": 0.83,
                "cadence_bpm": 73,
                "cadence_consistency": 0.79,
                "avg_energy": 0.49,
            },
            "independent": {
                "duration_seconds": 30,
                "voice_ratio_total": 0.78,
                "voice_ratio_student": None,
                "voice_ratio_guru": None,
                "pitch_stability": 0.86,
                "cadence_bpm": 71,
                "cadence_consistency": 0.82,
                "avg_energy": 0.52,
            },
        }

        stage_results: dict[str, dict[str, Any]] = {}
        stage_pass: dict[str, bool] = {}

        for stage, metrics in stage_metrics.items():
            resp = client.post(
                "/v1/maha-mantra/evaluate",
                json={
                    "stage": stage,
                    "lineage": "vaishnavism",
                    "golden_profile": "maha_mantra_v1",
                    "session_id": session_id,
                    "metrics": metrics,
                },
            )
            assert resp.status_code == 200, resp.text
            out = resp.json()
            stage_results[stage] = out
            stage_pass[stage] = bool(out["passes_golden"])

            evt = client.post(
                f"/v1/sessions/{session_id}/events",
                json={
                    "event_type": "maha_mantra_stage_eval",
                    "client_event_id": f"poc-{stage}",
                    "payload": {
                        "stage": stage,
                        "practice_seconds": metrics["duration_seconds"],
                        "flow_score": out["resonance"],
                        "pronunciation_score": out["coherence"],
                        "cadence_bpm": metrics["cadence_bpm"],
                        "adaptation_helpful": True,
                        "metrics": metrics,
                        "result": out,
                    },
                },
            )
            assert evt.status_code == 201, evt.text

        lineage_matrix: dict[str, dict[str, Any]] = {}
        for lineage in ["sadhguru", "shree_vallabhacharya", "vaishnavism"]:
            lineage_eval = client.post(
                "/v1/maha-mantra/evaluate",
                json={
                    "stage": "independent",
                    "lineage": lineage,
                    "golden_profile": "maha_mantra_v1",
                    "session_id": session_id,
                    "metrics": stage_metrics["independent"],
                },
            )
            assert lineage_eval.status_code == 200, lineage_eval.text
            lineage_matrix[lineage] = lineage_eval.json()

        end = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 5, "completed_goal": stage_pass.get("independent", False)},
        )
        assert end.status_code == 200, end.text

        bhav = client.post(
            f"/v1/sessions/{session_id}/bhav",
            json={
                "lineage": "vaishnavism",
                "golden_profile": "maha_mantra_v1",
                "persist": False,
            },
        )
        assert bhav.status_code == 200, bhav.text

        bhav_json = bhav.json()

    overall_composite = _mean([float(v["composite"]) for v in stage_results.values()])
    all_stage_pass = all(stage_pass.values())

    checks = [
        {
            "id": "poc_ui_served",
            "passed": ui_ok,
            "evidence": "/poc/ responds with Maha Mantra UI",
        },
        {
            "id": "stage_eval_api_contract",
            "passed": len(stage_results) == 3,
            "evidence": "guided + call_response + independent evaluations returned",
        },
        {
            "id": "stage_scores_golden_pass",
            "passed": all_stage_pass,
            "evidence": stage_pass,
        },
        {
            "id": "lineage_matrix_supported",
            "passed": all(bool(v.get("passes_golden", False)) for v in lineage_matrix.values()),
            "evidence": {
                lineage: {
                    "lineage_id": result.get("lineage_id"),
                    "composite": result.get("composite"),
                    "passes_golden": result.get("passes_golden"),
                }
                for lineage, result in lineage_matrix.items()
            },
        },
        {
            "id": "session_data_layer_connected",
            "passed": True,
            "evidence": "stage eval events were ingested into session_events",
        },
        {
            "id": "bhav_post_session",
            "passed": bool(bhav_json.get("passes_golden", False)),
            "evidence": {
                "composite": bhav_json.get("composite"),
                "passes_golden": bhav_json.get("passes_golden"),
            },
        },
    ]

    readiness = round(_mean([1.0 if c["passed"] else 0.0 for c in checks]), 3)
    critical_pass = checks[0]["passed"] and checks[2]["passed"] and checks[5]["passed"]

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "goal": "Working Maha Mantra web POC with staged learning and scoring",
        "summary": {
            "ready_for_live_demo": critical_pass,
            "readiness_score_0_to_1": readiness,
            "overall_stage_composite": round(_clamp01(overall_composite), 3),
        },
        "checks": checks,
        "stage_results": stage_results,
        "lineage_matrix": lineage_matrix,
        "bhav": bhav_json,
    }


def main() -> int:
    report = _run_scenario()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote Maha Mantra POC report: {REPORT_PATH}")

    return 0 if report["summary"]["ready_for_live_demo"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
