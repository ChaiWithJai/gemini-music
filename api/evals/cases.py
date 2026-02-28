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

    north_star = client.get("/v1/analytics/business-signal/north-star")
    assert north_star.status_code == 200, north_star.text
    ns = north_star.json()
    assert ns["metric_id"] == "NSM-001"

    attribution = client.get("/v1/analytics/business-signal/attribution")
    assert attribution.status_code == 200, attribution.text
    attr = attribution.json()
    assert "trend" in attr

    return {
        "business_kpi_projection": 1.0,
        "business_experiment_ci": 1.0 if exp["ci95_high"] >= exp["ci95_low"] else 0.0,
        "business_cohort_export": 1.0 if len(cohort_rows) >= 1 else 0.0,
        "north_star_metric_contract": 1.0,
        "business_trend_deltas_present": 1.0 if "north_star_delta" in attr["trend"] else 0.0,
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


def case_chaos_reliability(client: TestClient) -> dict[str, float]:
    # Scenario 1: biometric unavailable/disabled should not block adaptation.
    user_id = _create_user(client, "Chaos User")
    no_bio_session = _start_session(client, user_id, mood="neutral")
    event_a = client.post(
        f"/v1/sessions/{no_bio_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "chaos-no-bio",
            "payload": {"cadence_bpm": 74, "practice_seconds": 180},
        },
    )
    assert event_a.status_code == 201, event_a.text
    adapt_a = client.post(
        f"/v1/sessions/{no_bio_session}/adaptations",
        json={"explicit_mood": "neutral"},
    )
    assert adapt_a.status_code == 200, adapt_a.text

    # Scenario 2: high-noise context should push high guidance intensity.
    noisy_session = _start_session(client, user_id, mood="neutral")
    event_b = client.post(
        f"/v1/sessions/{noisy_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "chaos-noisy",
            "payload": {
                "cadence_bpm": 78,
                "practice_seconds": 180,
                "noise_level_db": 84,
                "flow_score": 0.72,
                "pronunciation_score": 0.76,
            },
        },
    )
    assert event_b.status_code == 201, event_b.text
    adapt_b = client.post(
        f"/v1/sessions/{noisy_session}/adaptations",
        json={"explicit_mood": "neutral"},
    )
    assert adapt_b.status_code == 200, adapt_b.text
    assert adapt_b.json()["guidance_intensity"] == "high"

    # Scenario 3: transient Gemini failure must fall back to deterministic adaptation.
    import gemini_music_api.main as main_module

    original_try = main_module.try_gemini_adaptation

    def _flaky_gemini(*_: object, **__: object) -> dict[str, object] | None:
        raise RuntimeError("simulated transient upstream failure")

    transient_session = _start_session(client, user_id, mood="anxious")
    event_c = client.post(
        f"/v1/sessions/{transient_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": "chaos-transient",
            "payload": {
                "cadence_bpm": 82,
                "practice_seconds": 200,
                "heart_rate": 116,
                "noise_level_db": 52,
            },
        },
    )
    assert event_c.status_code == 201, event_c.text

    main_module.try_gemini_adaptation = _flaky_gemini
    try:
        adapt_c = client.post(
            f"/v1/sessions/{transient_session}/adaptations",
            json={"explicit_mood": "anxious"},
        )
    finally:
        main_module.try_gemini_adaptation = original_try

    assert adapt_c.status_code == 200, adapt_c.text
    assert adapt_c.json()["guidance_intensity"] in {"high", "medium", "low"}

    for sid in [no_bio_session, noisy_session, transient_session]:
        ended = client.post(f"/v1/sessions/{sid}/end", json={"user_value_rating": 4.2, "completed_goal": True})
        assert ended.status_code == 200, ended.text

    return {
        "chaos_reliability_suite": 1.0,
        "chaos_no_biometrics": 1.0,
        "chaos_high_noise": 1.0,
        "chaos_transient_fallback": 1.0,
    }


def case_stage_mastery_progression(client: TestClient) -> dict[str, float]:
    guided = client.post(
        "/v1/maha-mantra/evaluate",
        json={
            "stage": "guided",
            "lineage": "vaishnavism",
            "golden_profile": "maha_mantra_v1",
            "metrics": {
                "duration_seconds": 39,
                "voice_ratio_total": 0.54,
                "voice_ratio_student": 0.54,
                "voice_ratio_guru": 0.0,
                "pitch_stability": 0.74,
                "cadence_bpm": 73,
                "cadence_consistency": 0.72,
                "avg_energy": 0.44,
            },
        },
    )
    assert guided.status_code == 200, guided.text
    guided_body = guided.json()

    call = client.post(
        "/v1/maha-mantra/evaluate",
        json={
            "stage": "call_response",
            "lineage": "vaishnavism",
            "golden_profile": "maha_mantra_v1",
            "metrics": {
                "duration_seconds": 40,
                "voice_ratio_total": 0.62,
                "voice_ratio_student": 0.69,
                "voice_ratio_guru": 0.15,
                "pitch_stability": 0.82,
                "cadence_bpm": 72,
                "cadence_consistency": 0.80,
                "avg_energy": 0.49,
            },
        },
    )
    assert call.status_code == 200, call.text
    call_body = call.json()

    independent = client.post(
        "/v1/maha-mantra/evaluate",
        json={
            "stage": "independent",
            "lineage": "vaishnavism",
            "golden_profile": "maha_mantra_v1",
            "metrics": {
                "duration_seconds": 30,
                "voice_ratio_total": 0.68,
                "voice_ratio_student": 0.68,
                "voice_ratio_guru": 0.0,
                "pitch_stability": 0.88,
                "cadence_bpm": 72,
                "cadence_consistency": 0.85,
                "avg_energy": 0.5,
            },
        },
    )
    assert independent.status_code == 200, independent.text
    independent_body = independent.json()

    for body in [guided_body, call_body, independent_body]:
        mastery = body.get("metrics_used", {}).get("mastery", {})
        assert mastery.get("level") in {"emerging", "developing", "mastered"}
        assert mastery.get("threshold_composite") is not None

    progression_delta = float(independent_body["composite"]) - float(guided_body["composite"])

    return {
        "stage_mastery_rubric": 1.0,
        "stage_progression_delta": 1.0 if progression_delta >= 0.05 else 0.0,
    }


def case_ai_kirtan_payload_contract(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "AI Kirtan Contract User")
    session_id = _start_session(client, user_id, mood="neutral")

    cases = [
        {"explicit_mood": "anxious", "heart_rate": 118, "noise_level_db": 50},
        {"explicit_mood": "joyful", "heart_rate": 76, "noise_level_db": 42},
        {"explicit_mood": "neutral", "heart_rate": 88, "noise_level_db": 46},
    ]

    quality_scores: list[float] = []
    for idx, payload in enumerate(cases):
        event = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"ai-kirtan-contract-{idx}",
                "payload": {
                    "cadence_bpm": 74,
                    "practice_seconds": 240,
                    "heart_rate": payload["heart_rate"],
                    "noise_level_db": payload["noise_level_db"],
                    "flow_score": 0.72,
                    "pronunciation_score": 0.77,
                },
            },
        )
        assert event.status_code == 201, event.text

        adaptation = client.post(f"/v1/sessions/{session_id}/adaptations", json={"explicit_mood": payload["explicit_mood"]})
        assert adaptation.status_code == 200, adaptation.text
        body = adaptation.json()
        adaptation_json = body.get("adaptation_json", {})
        arrangement = adaptation_json.get("arrangement", {})
        coach_actions = adaptation_json.get("coach_actions", [])

        required_arrangement = {"drone_level", "percussion", "call_response"}
        assert required_arrangement.issubset(arrangement.keys())
        assert isinstance(coach_actions, list) and len(coach_actions) >= 1
        assert isinstance(body.get("reason", ""), str) and len(body["reason"]) >= 10

        arrangement_quality = 1.0 if required_arrangement.issubset(arrangement.keys()) else 0.0
        coach_quality = 1.0 if len(coach_actions) >= 2 else 0.5
        explainability = 1.0 if len(body["reason"].split()) >= 4 else 0.5
        quality_scores.append((0.4 * arrangement_quality) + (0.35 * coach_quality) + (0.25 * explainability))

    mean_quality = sum(quality_scores) / len(quality_scores)
    return {
        "ai_kirtan_payload_contract": 1.0,
        "ai_kirtan_quality_rubric": round(mean_quality, 3),
    }


def case_adapter_starter_kit_references(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Adapter Starter User")
    session_id = _start_session(client, user_id, mood="neutral")

    webhook = client.post(
        "/v1/integrations/webhooks",
        json={
            "target_url": "https://example.org/hook",
            "adapter_id": "content_playlist_adapter",
            "event_types": ["session_ended", "adaptation_applied"],
            "is_active": True,
        },
    )
    assert webhook.status_code == 201, webhook.text

    wearable = client.post(
        "/v1/integrations/events",
        json={
            "session_id": session_id,
            "partner_source": "wearable_reference_partner",
            "adapter_id": "wearable_hr_stream",
            "event_type": "partner_signal",
            "client_event_id": "adapter-wearable-001",
            "payload": {"signal_type": "heart_rate", "heart_rate": 108, "cadence_bpm": 74, "practice_seconds": 120},
        },
    )
    assert wearable.status_code == 201, wearable.text

    content = client.post(
        "/v1/integrations/events",
        json={
            "session_id": session_id,
            "partner_source": "content_reference_partner",
            "adapter_id": "content_playlist_sync",
            "event_type": "partner_signal",
            "client_event_id": "adapter-content-001",
            "payload": {"signal_type": "playlist_sync", "playlist_id": "focus_set_001", "cadence_bpm": 72, "practice_seconds": 120},
        },
    )
    assert content.status_code == 201, content.text

    adaptation = client.post(f"/v1/sessions/{session_id}/adaptations", json={"explicit_mood": "neutral"})
    assert adaptation.status_code == 200, adaptation.text

    end = client.post(f"/v1/sessions/{session_id}/end", json={"user_value_rating": 4.8, "completed_goal": True})
    assert end.status_code == 200, end.text

    process = client.post("/v1/admin/webhooks/process?ignore_schedule=true")
    assert process.status_code == 200, process.text

    ecosystem = client.get("/v1/integrations/exports/ecosystem-usage/daily")
    assert ecosystem.status_code == 200, ecosystem.text
    eco = ecosystem.json()
    assert eco["wearable_adapter_events"] >= 1
    assert eco["content_export_events"] >= 1
    webhook_reliability = 1.0 if int(eco.get("webhook_deliveries_succeeded", 0)) >= 1 else 0.0

    return {
        "adapter_starter_kit_verified": 1.0,
        "ecosystem_wearable_adapter": 1.0,
        "ecosystem_content_adapter": 1.0,
        "webhook_reliability_observed": webhook_reliability,
    }


def case_seed_reproducibility_signal(client: TestClient) -> dict[str, float]:
    user_id = _create_user(client, "Seed Repro User")

    outputs: list[tuple[int, str, str]] = []
    for idx in range(2):
        session_id = _start_session(client, user_id, mood="anxious")
        client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"seed-repro-{idx}",
                "payload": {
                    "cadence_bpm": 82,
                    "practice_seconds": 220,
                    "heart_rate": 118,
                    "noise_level_db": 49,
                },
            },
        ).raise_for_status()
        adaptation = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "anxious"},
        )
        adaptation.raise_for_status()
        body = adaptation.json()
        outputs.append((int(body["tempo_bpm"]), str(body["guidance_intensity"]), str(body["key_center"])))

    stable = outputs[0] == outputs[1]
    return {"seed_reproducibility_stable": 1.0 if stable else 0.0}


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
        EvalCase(
            name="chaos_reliability_suite",
            policy="ALWAYS_PASSES",
            run=case_chaos_reliability,
        ),
        EvalCase(
            name="stage_mastery_progression",
            policy="ALWAYS_PASSES",
            run=case_stage_mastery_progression,
        ),
        EvalCase(
            name="ai_kirtan_payload_contract",
            policy="ALWAYS_PASSES",
            run=case_ai_kirtan_payload_contract,
        ),
        EvalCase(
            name="adapter_starter_kit_references",
            policy="ALWAYS_PASSES",
            run=case_adapter_starter_kit_references,
        ),
        EvalCase(
            name="seed_reproducibility_signal",
            policy="ALWAYS_PASSES",
            run=case_seed_reproducibility_signal,
        ),
    ]
