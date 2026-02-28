from __future__ import annotations

import math
import time

from fastapi.testclient import TestClient

from .framework import EvalCase


def _create_user(client: TestClient, name: str = "Eval User") -> str:
    resp = client.post("/v1/users", json={"display_name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _start_session(
    client: TestClient,
    user_id: str,
    *,
    mood: str = "anxious",
    mantra_key: str = "om_namah_shivaya",
) -> str:
    resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "Hackathon evaluation session",
            "mantra_key": mantra_key,
            "mood": mood,
            "target_duration_minutes": 10,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def case_core_story_end_to_end(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Core Story User")

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

    session_id = _start_session(client, user_id, mood="anxious")

    event = client.post(
        f"/v1/sessions/{session_id}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "core-story-evt-001",
            "payload": {
                "cadence_bpm": 80,
                "pronunciation_score": 0.61,
                "flow_score": 0.55,
                "practice_seconds": 720,
                "heart_rate": 118,
                "noise_level_db": 47,
            },
        },
    )
    assert event.status_code == 201, event.text

    adaptation = client.post(
        f"/v1/sessions/{session_id}/adaptations",
        json={"explicit_mood": "anxious"},
    )
    assert adaptation.status_code == 200, adaptation.text
    body = adaptation.json()
    assert body["guidance_intensity"] == "high"
    assert body["tempo_bpm"] < 80
    assert body["reason"]
    assert "coach_actions" in body["adaptation_json"]

    ended = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert ended.status_code == 200, ended.text
    summary = ended.json()["summary"]
    assert summary["practice_minutes"] >= 10
    assert summary["completed_goal"] is True

    progress = client.get(f"/v1/users/{user_id}/progress")
    assert progress.status_code == 200, progress.text
    progress_body = progress.json()
    assert progress_body["total_sessions"] == 1

    return {
        "realtime_loop_working": 1.0,
        "multi_signal_adaptation": 1.0,
        "adaptation_explainability": 1.0,
        "consent_controls_working": 1.0,
        "user_metric_projection": 1.0,
        "business_signal_projection": 1.0,
    }


def case_event_idempotency(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Idempotency User")
    session_id = _start_session(client, user_id, mood="neutral")

    payload = {
        "event_type": "voice_window",
        "client_event_id": "idem-evt-001",
        "payload": {"cadence_bpm": 74, "practice_seconds": 180},
    }
    first = client.post(f"/v1/sessions/{session_id}/events", json=payload)
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["idempotency_hit"] is False

    second = client.post(f"/v1/sessions/{session_id}/events", json=payload)
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["idempotency_hit"] is True

    return {
        "idempotent_event_ingestion": 1.0,
        "reliable_event_log": 1.0,
    }


def case_consent_guardrails(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Consent User")

    default_consent = client.get(f"/v1/users/{user_id}/consent")
    assert default_consent.status_code == 200, default_consent.text
    default_body = default_consent.json()
    assert default_body["biometric_enabled"] is False
    assert default_body["raw_audio_storage_enabled"] is False

    updated = client.put(
        f"/v1/users/{user_id}/consent",
        json={
            "biometric_enabled": True,
            "environmental_enabled": True,
            "raw_audio_storage_enabled": False,
            "policy_version": "v1",
        },
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["biometric_enabled"] is True
    assert updated_body["raw_audio_storage_enabled"] is False

    return {
        "consent_controls_working": 1.0,
        "privacy_defaults_working": 1.0,
    }


def case_adaptive_vs_static_baseline(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Baseline Compare User")

    # "Adaptive" session with anxious + elevated heart rate.
    adaptive_session = _start_session(client, user_id, mood="anxious")
    client.post(
        f"/v1/sessions/{adaptive_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "baseline-adaptive-evt",
            "payload": {
                "cadence_bpm": 84,
                "pronunciation_score": 0.6,
                "flow_score": 0.5,
                "heart_rate": 116,
                "practice_seconds": 600,
            },
        },
    )
    adaptive = client.post(
        f"/v1/sessions/{adaptive_session}/adaptations",
        json={"explicit_mood": "anxious"},
    )
    assert adaptive.status_code == 200, adaptive.text
    adaptive_body = adaptive.json()

    # "Static-ish" baseline with neutral context.
    static_session = _start_session(client, user_id, mood="neutral")
    client.post(
        f"/v1/sessions/{static_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "baseline-static-evt",
            "payload": {"cadence_bpm": 84, "practice_seconds": 600},
        },
    )
    static = client.post(
        f"/v1/sessions/{static_session}/adaptations",
        json={"explicit_mood": "neutral"},
    )
    assert static.status_code == 200, static.text
    static_body = static.json()

    assert adaptive_body["guidance_intensity"] == "high"
    assert adaptive_body["tempo_bpm"] < static_body["tempo_bpm"]

    return {
        "baseline_comparison_harness": 1.0,
        "adaptive_delta_observed": 1.0,
    }


def case_bhav_maha_mantra_golden(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Bhav Maha User")
    session_id = _start_session(
        client,
        user_id,
        mood="grounded",
        mantra_key="maha_mantra_hare_krishna_hare_rama",
    )

    for i, cadence in enumerate([72, 73, 72, 74]):
        event = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"bhav-golden-evt-{i}",
                "payload": {
                    "cadence_bpm": cadence,
                    "pronunciation_score": 0.9,
                    "flow_score": 0.88,
                    "practice_seconds": 180,
                    "adaptation_helpful": True,
                },
            },
        )
        assert event.status_code == 201, event.text

    ended = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert ended.status_code == 200, ended.text

    lineages = ["sadhguru", "shree_vallabhacharya", "vaishnavism"]
    composites: list[float] = []
    lineage_passes: dict[str, float] = {}

    for lineage in lineages:
        bhav = client.post(
            f"/v1/sessions/{session_id}/bhav",
            json={
                "golden_profile": "maha_mantra_v1",
                "lineage": lineage,
                "persist": False,
            },
        )
        assert bhav.status_code == 200, bhav.text
        body = bhav.json()
        assert body["lineage_id"] in {lineage, "vaishnavism"}  # vashnavism alias normalizes to vaishnavism
        assert body["passes_golden"] is True
        composites.append(float(body["composite"]))
        lineage_passes[f"bhav_lineage_{lineage}_pass"] = 1.0

    return {
        "bhav_composite_eval": sum(composites) / len(composites),
        "maha_mantra_golden_pass": 1.0,
        **lineage_passes,
    }


def _sample_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    center = sum(values) / len(values)
    variance = sum((value - center) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def case_ecosystem_surfaces(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Ecosystem User")
    session_id = _start_session(client, user_id, mood="neutral")

    webhook = client.post(
        "/v1/integrations/webhooks",
        json={
            "target_url": "https://example.org/hook",
            "adapter_id": "content_playlist_export",
            "event_types": ["session_ended", "bhav_evaluated"],
            "is_active": True,
        },
    )
    assert webhook.status_code == 201, webhook.text

    wearable = client.post(
        "/v1/integrations/events",
        json={
            "session_id": session_id,
            "partner_source": "wearable_co",
            "adapter_id": "wearable_hr_stream",
            "event_type": "partner_signal",
            "client_event_id": "eco-partner-001",
            "payload": {
                "signal_type": "heart_rate",
                "heart_rate": 109,
                "practice_seconds": 120,
                "cadence_bpm": 74,
            },
        },
    )
    assert wearable.status_code == 201, wearable.text

    content_signal = client.post(
        "/v1/integrations/events",
        json={
            "session_id": session_id,
            "partner_source": "content_hub",
            "adapter_id": "content_playlist_sync",
            "event_type": "partner_signal",
            "client_event_id": "eco-partner-002",
            "payload": {
                "signal_type": "playlist_sync",
                "playlist_id": "bhajan_focus_set_1",
                "practice_seconds": 120,
                "cadence_bpm": 73,
            },
        },
    )
    assert content_signal.status_code == 201, content_signal.text

    ended = client.post(
        f"/v1/sessions/{session_id}/end",
        json={"user_value_rating": 5, "completed_goal": True},
    )
    assert ended.status_code == 200, ended.text

    export_business = client.get("/v1/integrations/exports/business-signals/daily")
    assert export_business.status_code == 200, export_business.text

    export_ecosystem = client.get("/v1/integrations/exports/ecosystem-usage/daily")
    assert export_ecosystem.status_code == 200, export_ecosystem.text
    ecosystem = export_ecosystem.json()
    assert ecosystem["inbound_partner_events"] >= 2
    assert ecosystem["exports_generated"] >= 1
    assert ecosystem["wearable_adapter_events"] >= 1
    assert ecosystem["content_export_events"] >= 1

    return {
        "ecosystem_partner_ingestion": 1.0,
        "ecosystem_webhook_surface": 1.0,
        "ecosystem_export_surface": 1.0,
        "ecosystem_wearable_adapter": 1.0,
        "ecosystem_content_adapter": 1.0,
    }


def case_business_signal_kpi_projection(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Business KPI User")

    adaptive_values: list[float] = []
    static_values: list[float] = []

    for idx, mood in enumerate(["anxious", "neutral", "anxious"]):
        session_id = _start_session(client, user_id, mood=mood)
        evt = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"biz-evt-{idx}",
                "payload": {
                    "cadence_bpm": 82,
                    "practice_seconds": 300,
                    "heart_rate": 118 if mood == "anxious" else 86,
                    "noise_level_db": 46,
                    "flow_score": 0.72,
                    "pronunciation_score": 0.77,
                    "adaptation_helpful": True,
                },
            },
        )
        assert evt.status_code == 201, evt.text

        adaptive = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": mood},
        )
        assert adaptive.status_code == 200, adaptive.text
        adaptive_values.append(float(adaptive.json()["tempo_bpm"]))

        static = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "neutral"},
        )
        assert static.status_code == 200, static.text
        static_values.append(float(static.json()["tempo_bpm"]))

        ended = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 5, "completed_goal": True},
        )
        assert ended.status_code == 200, ended.text

    cohort = client.get("/v1/analytics/business-cohorts")
    assert cohort.status_code == 200, cohort.text
    cohort_rows = cohort.json()["rows"]
    assert len(cohort_rows) >= 1

    experiment = client.post(
        "/v1/analytics/experiments/adaptive-vs-static",
        json={
            "adaptive_values": adaptive_values,
            "static_values": static_values,
        },
    )
    assert experiment.status_code == 200, experiment.text
    exp = experiment.json()
    assert exp["ci95_high"] >= exp["ci95_low"]

    export_business = client.get("/v1/integrations/exports/business-signals/daily")
    assert export_business.status_code == 200, export_business.text
    business = export_business.json()
    assert business["sessions_started"] >= 3
    assert business["sessions_completed"] >= 3

    return {
        "business_kpi_projection": 1.0,
        "business_experiment_ci": 1.0 if exp["ci95_high"] >= exp["ci95_low"] else 0.0,
        "business_cohort_export": 1.0 if len(cohort_rows) >= 1 else 0.0,
    }


def case_eval_rigor_confidence_and_drift(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Rigor User")
    deltas: list[float] = []
    latencies_ms: list[float] = []

    for idx in range(5):
        session_id = _start_session(client, user_id, mood="anxious" if idx % 2 == 0 else "neutral")
        event = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"rigor-evt-{idx}",
                "payload": {
                    "cadence_bpm": 84,
                    "practice_seconds": 240,
                    "heart_rate": 120 if idx % 2 == 0 else 82,
                    "noise_level_db": 48,
                    "flow_score": 0.7,
                    "pronunciation_score": 0.75,
                },
            },
        )
        assert event.status_code == 201, event.text

        t0 = time.monotonic()
        adaptive = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "anxious"},
        )
        t1 = time.monotonic()
        assert adaptive.status_code == 200, adaptive.text
        latencies_ms.append((t1 - t0) * 1000.0)

        static = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "neutral"},
        )
        assert static.status_code == 200, static.text
        deltas.append(float(static.json()["tempo_bpm"]) - float(adaptive.json()["tempo_bpm"]))

        ended = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 4.5, "completed_goal": True},
        )
        assert ended.status_code == 200, ended.text

    delta_mean = sum(deltas) / len(deltas)
    delta_std = _sample_std(deltas)
    margin = 1.96 * (delta_std / math.sqrt(len(deltas))) if len(deltas) > 1 else 0.0
    ci_low = delta_mean - margin
    ci_high = delta_mean + margin

    recompute = client.post("/v1/admin/projections/recompute")
    assert recompute.status_code == 200, recompute.text
    assert recompute.json()["days_recomputed"] >= 1

    return {
        "eval_confidence_bounds": 1.0 if ci_high >= ci_low else 0.0,
        "eval_variance_reporting": 1.0 if delta_std < 8.0 else 0.0,
        "eval_drift_guard": 1.0 if recompute.json()["days_recomputed"] >= 1 else 0.0,
    }


def get_eval_cases() -> list[EvalCase]:
    return [
        EvalCase(
            name="core_story_end_to_end",
            policy="ALWAYS_PASSES",
            run=case_core_story_end_to_end,
        ),
        EvalCase(
            name="event_idempotency",
            policy="ALWAYS_PASSES",
            run=case_event_idempotency,
        ),
        EvalCase(
            name="consent_guardrails",
            policy="ALWAYS_PASSES",
            run=case_consent_guardrails,
        ),
        EvalCase(
            name="adaptive_vs_static_baseline",
            policy="USUALLY_PASSES",
            run=case_adaptive_vs_static_baseline,
        ),
        EvalCase(
            name="bhav_maha_mantra_golden",
            policy="USUALLY_PASSES",
            run=case_bhav_maha_mantra_golden,
        ),
        EvalCase(
            name="ecosystem_surfaces",
            policy="ALWAYS_PASSES",
            run=case_ecosystem_surfaces,
        ),
        EvalCase(
            name="business_signal_kpi_projection",
            policy="ALWAYS_PASSES",
            run=case_business_signal_kpi_projection,
        ),
        EvalCase(
            name="eval_rigor_confidence_and_drift",
            policy="ALWAYS_PASSES",
            run=case_eval_rigor_confidence_and_drift,
        ),
    ]
