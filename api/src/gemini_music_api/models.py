from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    biometric_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    environmental_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raw_audio_storage_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="api", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    mantra_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    mood: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SessionEvent(Base):
    __tablename__ = "session_events"
    __table_args__ = (
        UniqueConstraint("session_id", "client_event_id", name="uq_session_client_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    event_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    client_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ingestion_source: Mapped[str] = mapped_column(String(40), default="api", nullable=False)
    source_adapter: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AdaptationDecision(Base):
    __tablename__ = "adaptation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    decision_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    tempo_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    guidance_intensity: Mapped[str] = mapped_column(String(20), nullable=False)
    key_center: Mapped[str] = mapped_column(String(8), nullable=False)
    adaptation_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PracticeProgress(Base):
    __tablename__ = "practice_progress"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_practice_minutes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_flow_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_pronunciation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class BhavEvaluation(Base):
    __tablename__ = "bhav_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    mantra_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lineage_id: Mapped[str] = mapped_column(String(60), nullable=False, default="vaishnavism")
    profile_name: Mapped[str] = mapped_column(String(40), nullable=False, default="maha_mantra_v1")
    discipline: Mapped[float] = mapped_column(Float, nullable=False)
    resonance: Mapped[float] = mapped_column(Float, nullable=False)
    coherence: Mapped[float] = mapped_column(Float, nullable=False)
    composite: Mapped[float] = mapped_column(Float, nullable=False)
    passes_golden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    __table_args__ = (
        UniqueConstraint("session_id", "chunk_id", name="uq_audio_chunk_session_chunk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    round_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(120), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    t_start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    t_end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate_hz: Mapped[int] = mapped_column(Integer, nullable=False, default=16000)
    encoding: Mapped[str] = mapped_column(String(40), nullable=False, default="browser_metrics_v1")
    blob_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lineage_id: Mapped[str] = mapped_column(String(60), nullable=False, default="vaishnavism")
    golden_profile: Mapped[str] = mapped_column(String(40), nullable=False, default="maha_mantra_v1")
    features_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ingested_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class StageScoreProjection(Base):
    __tablename__ = "stage_score_projections"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "stage",
            "lineage_id",
            "golden_profile",
            name="uq_stage_score_projection",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    lineage_id: Mapped[str] = mapped_column(String(60), nullable=False, default="vaishnavism", index=True)
    golden_profile: Mapped[str] = mapped_column(String(40), nullable=False, default="maha_mantra_v1")
    discipline: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resonance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    coherence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    composite: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passes_golden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feedback_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    adapter_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("webhook_subscriptions.id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dead_letter_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class IntegrationExportLog(Base):
    __tablename__ = "integration_export_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    adapter_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class EcosystemUsageDaily(Base):
    __tablename__ = "ecosystem_usage_daily"

    date_key: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    inbound_partner_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_webhooks_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    webhook_deliveries_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    webhook_deliveries_retrying: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    webhook_dead_letters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    webhook_failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exports_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wearable_adapter_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_export_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_partner_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class BusinessSignalDaily(Base):
    __tablename__ = "business_signal_daily"

    date_key: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    sessions_started: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sessions_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meaningful_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_user_value_rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    adaptation_helpful_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    day7_returning_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_active_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bhav_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class EvalDriftSnapshot(Base):
    __tablename__ = "eval_drift_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_name: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rigor_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_score_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rigor_score_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempt_pass_rate_mean: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempt_pass_rate_std: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ci95_low: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ci95_high: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PASS", index=True)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
