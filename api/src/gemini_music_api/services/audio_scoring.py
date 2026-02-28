from __future__ import annotations

import datetime as dt
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AudioChunk, StageScoreProjection
from ..schemas import AudioChunkFeaturesIn, MahaMantraEvalOut, MahaMantraMetrics
from .bhav import DEFAULT_GOLDEN_PROFILE, resolve_lineage
from .gemini_scoring import try_gemini_stage_score
from .maha_mantra_eval import STAGE_TARGETS, evaluate_maha_mantra_stage


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def clamp01(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _weighted_mean(rows: list[tuple[float, float]], default: float) -> float:
    if not rows:
        return default
    total_weight = sum(weight for _, weight in rows)
    if total_weight <= 0:
        return default
    weighted = sum(value * weight for value, weight in rows)
    return weighted / total_weight


def normalize_audio_chunk(
    *,
    t_start_ms: int,
    t_end_ms: int,
    features: AudioChunkFeaturesIn,
) -> tuple[dict[str, Any], dict[str, float | None], float]:
    duration_seconds = float(features.duration_seconds) if features.duration_seconds is not None else (
        max(0.1, float(t_end_ms - t_start_ms) / 1000.0)
    )
    total_frames = int(features.total_frames or 0)
    voiced_frames = int(features.voiced_frames or 0)
    if total_frames > 0:
        voiced_frames = min(voiced_frames, total_frames)

    if features.voice_ratio_total is not None:
        voice_ratio_total = float(features.voice_ratio_total)
    elif total_frames > 0:
        voice_ratio_total = float(voiced_frames) / float(total_frames)
    else:
        voice_ratio_total = 0.0

    metrics = {
        "duration_seconds": round(max(0.1, duration_seconds), 3),
        "voice_ratio_total": round(clamp01(voice_ratio_total), 3),
        "voice_ratio_student": (
            None if features.voice_ratio_student is None else round(clamp01(features.voice_ratio_student), 3)
        ),
        "voice_ratio_guru": (
            None if features.voice_ratio_guru is None else round(clamp01(features.voice_ratio_guru), 3)
        ),
        "pitch_stability": round(clamp01(features.pitch_stability if features.pitch_stability is not None else 0.5), 3),
        "cadence_bpm": round(
            float(features.cadence_bpm) if features.cadence_bpm is not None else 72.0,
            2,
        ),
        "cadence_consistency": round(
            clamp01(features.cadence_consistency if features.cadence_consistency is not None else 0.5),
            3,
        ),
        "avg_energy": round(clamp01(features.avg_energy if features.avg_energy is not None else 0.5), 3),
    }

    snr_db = float(features.snr_db) if features.snr_db is not None else None
    snr_norm = clamp01((snr_db - 5.0) / 25.0) if snr_db is not None else 0.5
    signal_quality = mean(
        [
            metrics["voice_ratio_total"],
            metrics["pitch_stability"],
            metrics["cadence_consistency"],
        ]
    )
    chunk_confidence = round(clamp01((0.6 * signal_quality) + (0.4 * snr_norm)), 3)

    features_json: dict[str, Any] = {
        "duration_seconds": metrics["duration_seconds"],
        "total_frames": total_frames,
        "voiced_frames": voiced_frames,
        "snr_db": snr_db,
        "voice_ratio_total": metrics["voice_ratio_total"],
        "voice_ratio_student": metrics["voice_ratio_student"],
        "voice_ratio_guru": metrics["voice_ratio_guru"],
        "pitch_stability": metrics["pitch_stability"],
        "cadence_bpm": metrics["cadence_bpm"],
        "cadence_consistency": metrics["cadence_consistency"],
        "avg_energy": metrics["avg_energy"],
    }
    return features_json, metrics, chunk_confidence


def _aggregate_stage_metrics(chunks: list[AudioChunk]) -> tuple[MahaMantraMetrics, dict[str, Any]]:
    if not chunks:
        raise ValueError("No audio chunks available for aggregation")

    duration_weights: list[float] = []
    duration_total = 0.0
    cadence_rows: list[tuple[float, float]] = []
    pitch_rows: list[tuple[float, float]] = []
    consistency_rows: list[tuple[float, float]] = []
    energy_rows: list[tuple[float, float]] = []
    voice_total_rows: list[tuple[float, float]] = []
    student_rows: list[tuple[float, float]] = []
    guru_rows: list[tuple[float, float]] = []
    snr_values: list[float] = []

    for chunk in chunks:
        m = chunk.metrics_json or {}
        f = chunk.features_json or {}
        duration = max(0.1, float(m.get("duration_seconds") or f.get("duration_seconds") or 0.1))
        duration_weights.append(duration)
        duration_total += duration

        cadence_rows.append((float(m.get("cadence_bpm", 72.0)), duration))
        pitch_rows.append((clamp01(m.get("pitch_stability")), duration))
        consistency_rows.append((clamp01(m.get("cadence_consistency")), duration))
        energy_rows.append((clamp01(m.get("avg_energy")), duration))
        voice_total_rows.append((clamp01(m.get("voice_ratio_total")), duration))

        if m.get("voice_ratio_student") is not None:
            student_rows.append((clamp01(m.get("voice_ratio_student")), duration))
        if m.get("voice_ratio_guru") is not None:
            guru_rows.append((clamp01(m.get("voice_ratio_guru")), duration))

        snr_db = f.get("snr_db")
        if isinstance(snr_db, (int, float)):
            snr_values.append(float(snr_db))

    metrics = MahaMantraMetrics(
        duration_seconds=round(duration_total, 3),
        voice_ratio_total=round(_weighted_mean(voice_total_rows, 0.0), 3),
        voice_ratio_student=(
            round(_weighted_mean(student_rows, 0.0), 3) if student_rows else None
        ),
        voice_ratio_guru=round(_weighted_mean(guru_rows, 0.0), 3) if guru_rows else None,
        pitch_stability=round(_weighted_mean(pitch_rows, 0.5), 3),
        cadence_bpm=round(_weighted_mean(cadence_rows, 72.0), 2),
        cadence_consistency=round(_weighted_mean(consistency_rows, 0.5), 3),
        avg_energy=round(_weighted_mean(energy_rows, 0.5), 3),
    )

    info = {
        "duration_total_seconds": round(duration_total, 3),
        "chunk_count": len(chunks),
        "snr_mean_db": round(mean(snr_values), 3) if snr_values else None,
    }
    return metrics, info


def recompute_stage_projection(
    db: Session,
    *,
    session_id: str,
    stage: str,
    lineage_id: str,
    golden_profile: str = DEFAULT_GOLDEN_PROFILE,
) -> StageScoreProjection:
    chunks = db.scalars(
        select(AudioChunk)
        .where(
            AudioChunk.session_id == session_id,
            AudioChunk.stage == stage,
            AudioChunk.lineage_id == lineage_id,
            AudioChunk.golden_profile == golden_profile,
        )
        .order_by(AudioChunk.seq.asc(), AudioChunk.id.asc())
    ).all()
    if not chunks:
        raise ValueError("No chunks for stage projection")

    metrics, aggregate_info = _aggregate_stage_metrics(chunks)
    lineage = resolve_lineage(lineage_id)
    deterministic_result = evaluate_maha_mantra_stage(
        stage=stage,
        metrics=metrics,
        lineage=lineage,
        golden_profile=golden_profile,
    )
    result: MahaMantraEvalOut = deterministic_result
    gemini_payload, gemini_meta = try_gemini_stage_score(
        stage=stage,
        lineage=lineage,
        golden_profile=golden_profile,
        metrics=metrics,
        deterministic_eval=deterministic_result,
        aggregate_info=aggregate_info,
    )

    scorer_source = "deterministic"
    scorer_model: str | None = None
    scorer_confidence = 0.0
    scorer_evidence_json: dict[str, Any] = {
        "fallback_reason": gemini_meta.get("reason", "disabled"),
        "gemini_attempted": bool(gemini_meta.get("attempted", False)),
    }
    if gemini_meta.get("attempted"):
        scorer_model = gemini_meta.get("model")
        scorer_evidence_json["model"] = gemini_meta.get("model")

    if gemini_payload is not None:
        scorer_source = "gemini"
        scorer_model = str(gemini_meta.get("model")) if gemini_meta.get("model") else None
        scorer_confidence = float(gemini_payload["scorer_confidence"])
        scorer_evidence_json = {
            **dict(gemini_payload.get("evidence_json") or {}),
            "gemini_meta": gemini_meta,
        }
        result = MahaMantraEvalOut(
            stage=stage,
            lineage_id=lineage.id,
            golden_profile=golden_profile,
            discipline=float(gemini_payload["discipline"]),
            resonance=float(gemini_payload["resonance"]),
            coherence=float(gemini_payload["coherence"]),
            composite=float(gemini_payload["composite"]),
            passes_golden=bool(gemini_payload["passes_golden"]),
            feedback=list(gemini_payload["feedback"]),
            metrics_used=dict(gemini_payload.get("metrics_used") or deterministic_result.metrics_used),
        )

    target_duration = float(STAGE_TARGETS[stage]["duration_seconds"])
    coverage_ratio = clamp01(float(metrics.duration_seconds) / max(1.0, target_duration))
    snr_mean_db = aggregate_info.get("snr_mean_db")
    snr_norm = clamp01((float(snr_mean_db) - 5.0) / 25.0) if snr_mean_db is not None else 0.5
    signal_quality = mean(
        [
            clamp01(metrics.voice_ratio_total),
            clamp01(metrics.pitch_stability),
            clamp01(metrics.cadence_consistency),
        ]
    )
    confidence = round(clamp01((0.55 * coverage_ratio) + (0.25 * snr_norm) + (0.20 * signal_quality)), 3)

    projection = db.scalars(
        select(StageScoreProjection).where(
            StageScoreProjection.session_id == session_id,
            StageScoreProjection.stage == stage,
            StageScoreProjection.lineage_id == lineage.id,
            StageScoreProjection.golden_profile == golden_profile,
        )
    ).first()
    if projection is None:
        projection = StageScoreProjection(
            session_id=session_id,
            stage=stage,
            lineage_id=lineage.id,
            golden_profile=golden_profile,
        )
        db.add(projection)

    projection.discipline = float(result.discipline)
    projection.resonance = float(result.resonance)
    projection.coherence = float(result.coherence)
    projection.composite = float(result.composite)
    projection.passes_golden = bool(result.passes_golden)
    projection.confidence = confidence
    projection.scorer_source = scorer_source
    projection.scorer_model = scorer_model
    projection.scorer_confidence = round(clamp01(scorer_confidence), 3)
    projection.scorer_evidence_json = scorer_evidence_json
    projection.coverage_ratio = round(coverage_ratio, 3)
    projection.source_chunk_count = int(aggregate_info["chunk_count"])
    projection.metrics_json = {
        **result.metrics_used,
        "aggregate": aggregate_info,
        "scorer": {
            "source": scorer_source,
            "model": scorer_model,
            "reason": gemini_meta.get("reason"),
            "scorer_confidence": round(clamp01(scorer_confidence), 3),
        },
    }
    projection.feedback_json = list(result.feedback)
    projection.updated_at = _utcnow()
    db.flush()
    return projection
