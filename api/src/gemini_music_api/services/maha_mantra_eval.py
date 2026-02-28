from __future__ import annotations

from typing import Any

from ..schemas import MahaMantraMetrics, MahaMantraEvalOut
from .bhav import DEFAULT_GOLDEN_PROFILE, LineageProfile, clamp01


STAGE_TARGETS: dict[str, dict[str, float]] = {
    "guided": {"duration_seconds": 45.0, "threshold_offset": -0.08},
    "call_response": {"duration_seconds": 40.0, "threshold_offset": -0.04},
    "independent": {"duration_seconds": 30.0, "threshold_offset": 0.0},
}

STAGE_NEXT: dict[str, str | None] = {
    "guided": "call_response",
    "call_response": "independent",
    "independent": None,
}

TARGET_BPM = 72.0


def _cadence_accuracy(bpm: float) -> float:
    # +/- 24 BPM tolerance around the golden tempo.
    return clamp01(1.0 - (abs(float(bpm) - TARGET_BPM) / 24.0))


def _energy_centered_score(avg_energy: float) -> float:
    # Balanced devotional intensity is centered near 0.48.
    return clamp01(1.0 - (abs(float(avg_energy) - 0.48) / 0.48))


def _voice_ratio_student(metrics: MahaMantraMetrics) -> float:
    return float(metrics.voice_ratio_student) if metrics.voice_ratio_student is not None else float(
        metrics.voice_ratio_total
    )


def _voice_ratio_guru(metrics: MahaMantraMetrics) -> float:
    if metrics.voice_ratio_guru is not None:
        return float(metrics.voice_ratio_guru)
    student = _voice_ratio_student(metrics)
    return clamp01(float(metrics.voice_ratio_total) - student)


def _stage_scores(stage: str, metrics: MahaMantraMetrics) -> tuple[float, float, float, dict[str, float]]:
    duration_target = STAGE_TARGETS[stage]["duration_seconds"]
    duration_ratio = clamp01(float(metrics.duration_seconds) / duration_target)
    cadence_accuracy = _cadence_accuracy(float(metrics.cadence_bpm))
    energy_score = _energy_centered_score(float(metrics.avg_energy))
    voice_total = clamp01(float(metrics.voice_ratio_total))
    pitch_stability = clamp01(float(metrics.pitch_stability))
    cadence_consistency = clamp01(float(metrics.cadence_consistency))

    if stage == "guided":
        discipline = clamp01(
            (0.40 * duration_ratio)
            + (0.30 * voice_total)
            + (0.30 * cadence_consistency)
        )
        resonance = clamp01(
            (0.45 * pitch_stability)
            + (0.35 * energy_score)
            + (0.20 * cadence_accuracy)
        )
        coherence = clamp01((0.60 * pitch_stability) + (0.40 * cadence_consistency))
        stage_signals = {
            "duration_ratio": round(duration_ratio, 3),
            "voice_total": round(voice_total, 3),
            "cadence_consistency": round(cadence_consistency, 3),
        }
        return discipline, resonance, coherence, stage_signals

    if stage == "call_response":
        student_voice = _voice_ratio_student(metrics)
        guru_voice = _voice_ratio_guru(metrics)
        student_turn_balance = clamp01(1.0 - (abs(student_voice - 0.6) / 0.6))
        guru_listening = clamp01(1.0 - (guru_voice / 0.5))

        discipline = clamp01(
            (0.35 * duration_ratio)
            + (0.35 * student_turn_balance)
            + (0.30 * guru_listening)
        )
        resonance = clamp01(
            (0.40 * pitch_stability)
            + (0.35 * cadence_accuracy)
            + (0.25 * energy_score)
        )
        coherence = clamp01(
            (0.45 * pitch_stability)
            + (0.35 * cadence_consistency)
            + (0.20 * student_voice)
        )
        stage_signals = {
            "duration_ratio": round(duration_ratio, 3),
            "voice_student": round(student_voice, 3),
            "voice_guru": round(guru_voice, 3),
            "student_turn_balance": round(student_turn_balance, 3),
            "guru_listening": round(guru_listening, 3),
        }
        return discipline, resonance, coherence, stage_signals

    # independent
    discipline = clamp01(
        (0.45 * duration_ratio) + (0.35 * voice_total) + (0.20 * cadence_consistency)
    )
    resonance = clamp01((0.45 * pitch_stability) + (0.35 * energy_score) + (0.20 * voice_total))
    coherence = clamp01(
        (0.40 * pitch_stability)
        + (0.35 * cadence_consistency)
        + (0.25 * cadence_accuracy)
    )
    stage_signals = {
        "duration_ratio": round(duration_ratio, 3),
        "voice_total": round(voice_total, 3),
        "cadence_accuracy": round(cadence_accuracy, 3),
    }
    return discipline, resonance, coherence, stage_signals


def _feedback(
    *,
    stage: str,
    discipline: float,
    resonance: float,
    coherence: float,
    metrics: MahaMantraMetrics,
    thresholds: dict[str, float],
) -> list[str]:
    tips: list[str] = []

    if discipline < thresholds["discipline"]:
        tips.append("Keep steadier practice windows and stay consistent through the full stage duration.")
    if resonance < thresholds["resonance"]:
        tips.append("Match breath and vocal intensity to the track for stronger devotional resonance.")
    if coherence < thresholds["coherence"]:
        tips.append("Focus on cleaner syllable transitions and steadier note-to-note flow.")

    if float(metrics.cadence_consistency) < 0.65:
        tips.append("Use a calmer tempo anchor; avoid rushing at phrase boundaries.")
    if float(metrics.pitch_stability) < 0.65:
        tips.append("Hold each phrase slightly longer before transitioning to improve pitch stability.")

    if stage == "call_response":
        student_voice = _voice_ratio_student(metrics)
        guru_voice = _voice_ratio_guru(metrics)
        if student_voice < 0.45:
            tips.append("Increase voice presence during student turns in call-response.")
        if guru_voice > 0.35:
            tips.append("Leave more space during guru turns before your response.")

    if not tips:
        tips.append("Strong stage performance. Keep the same breath control and cadence consistency.")
    return tips[:4]


def evaluate_maha_mantra_stage(
    *,
    stage: str,
    metrics: MahaMantraMetrics,
    lineage: LineageProfile,
    golden_profile: str = DEFAULT_GOLDEN_PROFILE,
) -> MahaMantraEvalOut:
    if stage not in STAGE_TARGETS:
        raise ValueError(f"Unsupported stage: {stage}")

    discipline, resonance, coherence, stage_signals = _stage_scores(stage, metrics)

    composite = clamp01(
        (lineage.weights.discipline * discipline)
        + (lineage.weights.resonance * resonance)
        + (lineage.weights.coherence * coherence)
    )

    threshold_offset = STAGE_TARGETS[stage]["threshold_offset"]
    thresholds = {
        k: clamp01(v + threshold_offset) for k, v in lineage.thresholds.items()
    }

    passes_golden = golden_profile == DEFAULT_GOLDEN_PROFILE and all(
        [
            discipline >= thresholds["discipline"],
            resonance >= thresholds["resonance"],
            coherence >= thresholds["coherence"],
            composite >= thresholds["composite"],
        ]
    )

    feedback = _feedback(
        stage=stage,
        discipline=discipline,
        resonance=resonance,
        coherence=coherence,
        metrics=metrics,
        thresholds=thresholds,
    )

    cadence_target_gap = round(abs(float(metrics.cadence_bpm) - TARGET_BPM), 2)
    mastery_threshold = thresholds["composite"]
    mastery_gap = round(composite - mastery_threshold, 3)
    mastery_level = "emerging"
    if composite >= mastery_threshold + 0.08:
        mastery_level = "mastered"
    elif composite >= mastery_threshold:
        mastery_level = "developing"

    next_stage = STAGE_NEXT.get(stage)
    progression_ready = composite >= mastery_threshold
    metrics_used: dict[str, Any] = {
        "signals": stage_signals,
        "cadence_bpm": round(float(metrics.cadence_bpm), 2),
        "cadence_target_bpm": TARGET_BPM,
        "cadence_target_gap_bpm": cadence_target_gap,
        "pitch_stability": round(float(metrics.pitch_stability), 3),
        "avg_energy": round(float(metrics.avg_energy), 3),
        "thresholds": {k: round(v, 3) for k, v in thresholds.items()},
        "mastery": {
            "level": mastery_level,
            "threshold_composite": round(mastery_threshold, 3),
            "gap_to_threshold": mastery_gap,
            "progression_gate_passed": progression_ready,
            "next_stage": next_stage,
            "next_stage_hint": (
                f"Advance to {next_stage} with the same vocal stability focus."
                if progression_ready and next_stage
                else "Reinforce this stage before progressing."
            ),
        },
    }
    if stage == "call_response":
        metrics_used["voice_ratio_student"] = round(_voice_ratio_student(metrics), 3)
        metrics_used["voice_ratio_guru"] = round(_voice_ratio_guru(metrics), 3)
    else:
        metrics_used["voice_ratio_total"] = round(float(metrics.voice_ratio_total), 3)

    return MahaMantraEvalOut(
        stage=stage,
        lineage_id=lineage.id,
        golden_profile=golden_profile,
        discipline=round(discipline, 3),
        resonance=round(resonance, 3),
        coherence=round(coherence, 3),
        composite=round(composite, 3),
        passes_golden=passes_golden,
        feedback=feedback,
        metrics_used=metrics_used,
    )
