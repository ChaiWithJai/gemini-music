from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the app reads a test database URL before importing package modules.
TEST_DB_PATH = Path("/tmp/gemini_music_api_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app
from gemini_music_api.services.ai_kirtan_contract import verify_payload_contract


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_core_story_flow(client: TestClient) -> None:
    user_resp = client.post("/v1/users", json={"display_name": "Jay"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    consent_resp = client.put(
        f"/v1/users/{user_id}/consent",
        json={
            "biometric_enabled": True,
            "environmental_enabled": True,
            "raw_audio_storage_enabled": False,
            "policy_version": "v1",
        },
    )
    assert consent_resp.status_code == 200
    assert consent_resp.json()["biometric_enabled"] is True

    start_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Evening grounding",
            "mantra_key": "om_namah_shivaya",
            "mood": "anxious",
            "target_duration_minutes": 10,
        },
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["id"]

    event_payload = {
        "event_type": "voice_window",
        "client_event_id": "evt-001",
        "payload": {
            "cadence_bpm": 78,
            "pronunciation_score": 0.61,
            "flow_score": 0.52,
            "practice_seconds": 420,
            "heart_rate": 114,
            "noise_level_db": 48,
        },
    }
    first_event = client.post(f"/v1/sessions/{session_id}/events", json=event_payload)
    assert first_event.status_code == 201
    assert first_event.json()["idempotency_hit"] is False

    second_event = client.post(f"/v1/sessions/{session_id}/events", json=event_payload)
    assert second_event.status_code == 201
    assert second_event.json()["id"] == first_event.json()["id"]
    assert second_event.json()["idempotency_hit"] is True

    adaptation_resp = client.post(
        f"/v1/sessions/{session_id}/adaptations",
        json={"explicit_mood": "anxious"},
    )
    assert adaptation_resp.status_code == 200
    adaptation = adaptation_resp.json()
    assert adaptation["guidance_intensity"] == "high"
    assert adaptation["tempo_bpm"] <= 78

    end_resp = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert end_resp.status_code == 200
    summary = end_resp.json()["summary"]
    assert summary["completed_goal"] is True
    assert summary["meaningful_session"] is False  # <10 min in this test fixture

    progress_resp = client.get(f"/v1/users/{user_id}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["total_sessions"] == 1
    assert progress["completed_sessions"] == 1


def test_bhav_eval_maha_mantra_golden(client: TestClient) -> None:
    user_resp = client.post("/v1/users", json={"display_name": "Bhav User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    start_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Maha Mantra devotional practice",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": "grounded",
            "target_duration_minutes": 10,
        },
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["id"]

    # Stable cadence and strong quality signals to simulate a good devotional session.
    for i, cadence in enumerate([72, 73, 72, 74]):
        evt = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"bhav-evt-{i}",
                "payload": {
                    "cadence_bpm": cadence,
                    "pronunciation_score": 0.9,
                    "flow_score": 0.88,
                    "practice_seconds": 180,
                    "adaptation_helpful": True,
                },
            },
        )
        assert evt.status_code == 201

    end_resp = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert end_resp.status_code == 200

    lineages = ["sadhguru", "shree_vallabhacharya", "vashnavism"]
    for lineage in lineages:
        bhav_resp = client.post(
            f"/v1/sessions/{session_id}/bhav",
            json={"golden_profile": "maha_mantra_v1", "lineage": lineage, "persist": True},
        )
        assert bhav_resp.status_code == 200
        bhav = bhav_resp.json()

        assert bhav["profile_name"] == "maha_mantra_v1"
        assert bhav["lineage_id"] in {"sadhguru", "shree_vallabhacharya", "vaishnavism"}
        assert bhav["discipline"] >= 0.73
        assert bhav["resonance"] >= 0.70
        assert bhav["coherence"] >= 0.70
        assert bhav["composite"] >= 0.75
        assert bhav["passes_golden"] is True


def test_maha_mantra_stage_eval_endpoint(client: TestClient) -> None:
    payload = {
        "stage": "call_response",
        "lineage": "vashnavism",
        "golden_profile": "maha_mantra_v1",
        "metrics": {
            "duration_seconds": 40,
            "voice_ratio_total": 0.58,
            "voice_ratio_student": 0.74,
            "voice_ratio_guru": 0.16,
            "pitch_stability": 0.86,
            "cadence_bpm": 72,
            "cadence_consistency": 0.83,
            "avg_energy": 0.5,
        },
    }
    resp = client.post("/v1/maha-mantra/evaluate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "call_response"
    assert body["lineage_id"] == "vaishnavism"
    assert body["golden_profile"] == "maha_mantra_v1"
    assert body["composite"] >= 0.75
    assert body["passes_golden"] is True
    assert body["metrics_used"]["voice_ratio_student"] >= 0.7
    assert body["metrics_used"]["mastery"]["level"] in {"emerging", "developing", "mastered"}
    assert body["metrics_used"]["mastery"]["threshold_composite"] is not None
    assert isinstance(body["metrics_used"]["mastery"]["progression_gate_passed"], bool)
    assert len(body["feedback"]) >= 1


def test_maha_mantra_timing_endpoint(client: TestClient) -> None:
    resp = client.get("/v1/maha-mantra/timing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["track_id"] == "maha_mantra_lZXeUhUc8PM_v1"
    assert body["video_id"] == "lZXeUhUc8PM"
    assert body["listen_stage"]["start_sec"] == 18
    assert body["guided_stage"]["duration_sec"] == 45
    assert body["call_response_stage"]["duration_sec"] == 48
    assert len(body["call_response_stage"]["rounds"]) == 8
    assert body["independent_stage"]["duration_sec"] == 30


def test_audio_chunk_ingest_and_projection(client: TestClient) -> None:
    user_resp = client.post("/v1/users", json={"display_name": "Chunk User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    session_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Chunk scoring flow",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": "focused",
            "target_duration_minutes": 3,
        },
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    payload = {
        "stage": "guided",
        "chunk_id": "guided-001",
        "seq": 1,
        "t_start_ms": 48000,
        "t_end_ms": 93000,
        "sample_rate_hz": 16000,
        "encoding": "browser_metrics_v1",
        "lineage": "vaishnavism",
        "golden_profile": "maha_mantra_v1",
        "features": {
            "duration_seconds": 45,
            "total_frames": 450,
            "voiced_frames": 320,
            "voice_ratio_total": 0.71,
            "pitch_stability": 0.84,
            "cadence_bpm": 72,
            "cadence_consistency": 0.81,
            "avg_energy": 0.5,
            "snr_db": 18,
        },
    }

    first = client.post(f"/v1/sessions/{session_id}/audio/chunks", json=payload)
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["idempotency_hit"] is False
    assert first_body["stage"] == "guided"
    assert first_body["projection"]["stage"] == "guided"
    assert first_body["projection"]["source_chunk_count"] == 1
    assert first_body["projection"]["coverage_ratio"] >= 0.95
    assert first_body["projection"]["confidence"] > 0
    assert first_body["projection"]["scorer_source"] == "deterministic"
    assert first_body["projection"]["scorer_model"] is None
    assert first_body["projection"]["scorer_confidence"] == 0
    assert first_body["projection"]["composite"] >= 0.7

    second = client.post(f"/v1/sessions/{session_id}/audio/chunks", json=payload)
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["idempotency_hit"] is True
    assert second_body["projection"]["source_chunk_count"] == 1

    list_resp = client.get(f"/v1/sessions/{session_id}/stage-projections")
    assert list_resp.status_code == 200
    projections = list_resp.json()
    assert len(projections) == 1
    assert projections[0]["stage"] == "guided"
    assert projections[0]["source_chunk_count"] == 1
    assert projections[0]["scorer_source"] == "deterministic"


def test_audio_chunk_uses_gemini_scorer_when_available(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from gemini_music_api.services import audio_scoring

    def _fake_gemini_score(**_: object) -> tuple[dict[str, object], dict[str, object]]:
        return (
            {
                "discipline": 0.92,
                "resonance": 0.88,
                "coherence": 0.9,
                "composite": 0.9,
                "passes_golden": True,
                "feedback": ["Gemini scorer: strong devotional steadiness."],
                "scorer_confidence": 0.91,
                "evidence_json": {"mode": "stubbed"},
                "metrics_used": {"source": "gemini_stub"},
            },
            {
                "attempted": True,
                "model": "gemini-3-pro-preview",
                "reason": "ok",
            },
        )

    monkeypatch.setattr(audio_scoring, "try_gemini_stage_score", _fake_gemini_score)

    user_resp = client.post("/v1/users", json={"display_name": "Gemini Score User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    session_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Gemini chunk scoring flow",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": "focused",
            "target_duration_minutes": 3,
        },
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    payload = {
        "stage": "guided",
        "chunk_id": "guided-gemini-001",
        "seq": 1,
        "t_start_ms": 48000,
        "t_end_ms": 93000,
        "sample_rate_hz": 16000,
        "encoding": "browser_metrics_v1",
        "lineage": "vaishnavism",
        "golden_profile": "maha_mantra_v1",
        "features": {
            "duration_seconds": 45,
            "total_frames": 450,
            "voiced_frames": 320,
            "voice_ratio_total": 0.71,
            "pitch_stability": 0.84,
            "cadence_bpm": 72,
            "cadence_consistency": 0.81,
            "avg_energy": 0.5,
            "snr_db": 18,
        },
    }

    ingest_resp = client.post(f"/v1/sessions/{session_id}/audio/chunks", json=payload)
    assert ingest_resp.status_code == 201
    projection = ingest_resp.json()["projection"]
    assert projection["scorer_source"] == "gemini"
    assert projection["scorer_model"] == "gemini-3-pro-preview"
    assert projection["scorer_confidence"] == 0.91
    assert projection["feedback_json"][0].startswith("Gemini scorer:")
    assert projection["metrics_json"]["source"] == "gemini_stub"


def test_audio_chunk_falls_back_when_gemini_scorer_invalid(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from gemini_music_api.services import audio_scoring

    def _fake_failed_gemini_score(**_: object) -> tuple[None, dict[str, object]]:
        return (
            None,
            {
                "attempted": True,
                "model": "gemini-3-flash-preview",
                "reason": "invalid_payload",
            },
        )

    monkeypatch.setattr(audio_scoring, "try_gemini_stage_score", _fake_failed_gemini_score)

    user_resp = client.post("/v1/users", json={"display_name": "Fallback User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    session_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Fallback chunk scoring flow",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": "focused",
            "target_duration_minutes": 3,
        },
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    payload = {
        "stage": "guided",
        "chunk_id": "guided-fallback-001",
        "seq": 1,
        "t_start_ms": 48000,
        "t_end_ms": 93000,
        "sample_rate_hz": 16000,
        "encoding": "browser_metrics_v1",
        "lineage": "vaishnavism",
        "golden_profile": "maha_mantra_v1",
        "features": {
            "duration_seconds": 45,
            "total_frames": 450,
            "voiced_frames": 320,
            "voice_ratio_total": 0.71,
            "pitch_stability": 0.84,
            "cadence_bpm": 72,
            "cadence_consistency": 0.81,
            "avg_energy": 0.5,
            "snr_db": 18,
        },
    }

    ingest_resp = client.post(f"/v1/sessions/{session_id}/audio/chunks", json=payload)
    assert ingest_resp.status_code == 201
    projection = ingest_resp.json()["projection"]
    assert projection["scorer_source"] == "deterministic"
    assert projection["scorer_model"] == "gemini-3-flash-preview"
    assert projection["scorer_confidence"] == 0
    assert projection["scorer_evidence_json"]["fallback_reason"] == "invalid_payload"


def test_poc_static_ui_served(client: TestClient) -> None:
    resp = client.get("/poc/")
    assert resp.status_code == 200
    assert "Maha Mantra Learning Studio" in resp.text
    assert "/poc/app.js" in resp.text


def test_demo_static_ui_served(client: TestClient) -> None:
    resp = client.get("/demo/")
    assert resp.status_code == 200
    assert "Gemini Music Demo Console" in resp.text
    assert "/demo/demo.js" in resp.text


def test_integration_surfaces_and_exports(client: TestClient) -> None:
    user_resp = client.post("/v1/users", json={"display_name": "Integration User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    session_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Integration flow",
            "mantra_key": "om_namah_shivaya",
            "mood": "neutral",
            "target_duration_minutes": 10,
        },
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    webhook_resp = client.post(
        "/v1/integrations/webhooks",
        json={
            "target_url": "https://example.org/hook",
            "adapter_id": "content_playlist_export",
            "event_types": ["session_ended", "bhav_evaluated"],
            "is_active": True,
        },
    )
    assert webhook_resp.status_code == 201

    partner_event = client.post(
        "/v1/integrations/events",
        json={
            "session_id": session_id,
            "partner_source": "wearable_co",
            "adapter_id": "wearable_hr_stream",
            "event_type": "partner_signal",
            "client_event_id": "integration-evt-001",
            "payload": {
                "signal_type": "heart_rate",
                "heart_rate": 110,
                "cadence_bpm": 74,
                "practice_seconds": 180,
            },
        },
    )
    assert partner_event.status_code == 201
    assert partner_event.json()["ingestion_source"] == "partner:wearable_co"

    end_resp = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert end_resp.status_code == 200

    export_business = client.get("/v1/integrations/exports/business-signals/daily")
    assert export_business.status_code == 200

    export_ecosystem = client.get("/v1/integrations/exports/ecosystem-usage/daily")
    assert export_ecosystem.status_code == 200
    eco = export_ecosystem.json()
    assert eco["inbound_partner_events"] >= 1
    assert eco["exports_generated"] >= 1


def test_adaptive_vs_static_experiment_endpoint(client: TestClient) -> None:
    resp = client.post(
        "/v1/analytics/experiments/adaptive-vs-static",
        json={
            "adaptive_values": [0.84, 0.8, 0.83, 0.82],
            "static_values": [0.7, 0.71, 0.69, 0.7],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adaptive_mean"] > body["static_mean"]
    assert body["ci95_high"] >= body["ci95_low"]


def test_webhook_retry_and_dead_letter_observability(client: TestClient) -> None:
    user_resp = client.post("/v1/users", json={"display_name": "Webhook Retry User"})
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    session_resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Webhook resilience flow",
            "mantra_key": "om_namah_shivaya",
            "mood": "neutral",
            "target_duration_minutes": 8,
        },
    )
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    webhook_resp = client.post(
        "/v1/integrations/webhooks",
        json={
            "target_url": "https://example.org/fail-webhook",
            "adapter_id": "content_playlist_export",
            "event_types": ["session_ended"],
            "is_active": True,
        },
    )
    assert webhook_resp.status_code == 201

    end_resp = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 4.8, "completed_goal": True},
    )
    assert end_resp.status_code == 200

    # Drain retries immediately to converge to dead-letter without waiting.
    for _ in range(4):
        process = client.post("/v1/admin/webhooks/process?batch_size=50&ignore_schedule=true")
        assert process.status_code == 200

    ecosystem = client.get("/v1/integrations/exports/ecosystem-usage/daily")
    assert ecosystem.status_code == 200
    body = ecosystem.json()
    assert body["webhook_failed_attempts"] >= 1
    assert body["webhook_dead_letters"] >= 1

    north_star = client.get("/v1/analytics/business-signal/north-star")
    assert north_star.status_code == 200
    north_body = north_star.json()
    assert north_body["metric_id"] == "NSM-001"
    assert 0.0 <= north_body["value"] <= 1.0


def test_ai_kirtan_contract_verifier_rejects_missing_arrangement_fields() -> None:
    invalid_payload = {
        "tempo_bpm": 72,
        "guidance_intensity": "high",
        "key_center": "D",
        "reason": "calming adjustment for anxious mood",
        "adaptation_json": {
            "arrangement": {
                "drone_level": "medium",
                # missing "percussion" and "call_response"
            },
            "coach_actions": ["repeat_line"],
        },
    }
    passed, errors = verify_payload_contract(invalid_payload)
    assert passed is False
    assert any(err.startswith("missing_arrangement:") for err in errors)
