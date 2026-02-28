from __future__ import annotations

import datetime as dt
from typing import Literal
from typing import Any

from pydantic import BaseModel, Field


class APIModel(BaseModel):
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class UserOut(APIModel):
    id: str
    display_name: str
    created_at: dt.datetime


class ConsentUpdate(BaseModel):
    biometric_enabled: bool = False
    environmental_enabled: bool = True
    raw_audio_storage_enabled: bool = False
    policy_version: str = Field(default="v1", min_length=1, max_length=20)


class ConsentOut(APIModel):
    user_id: str
    biometric_enabled: bool
    environmental_enabled: bool
    raw_audio_storage_enabled: bool
    policy_version: str
    source: str
    created_at: dt.datetime


class SessionStartRequest(BaseModel):
    user_id: str
    intention: str = Field(min_length=1)
    mantra_key: str | None = None
    mood: str | None = None
    target_duration_minutes: int = Field(default=10, ge=1, le=180)


class SessionOut(APIModel):
    id: str
    user_id: str
    mantra_key: str | None
    intention: str
    mood: str | None
    target_duration_minutes: int
    status: str
    started_at: dt.datetime
    ended_at: dt.datetime | None
    summary_json: dict[str, Any] | None


class SessionEventIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=60)
    client_event_id: str | None = Field(default=None, max_length=120)
    schema_version: str = Field(default="v1", min_length=1, max_length=20)
    source_adapter: str | None = Field(default=None, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionEventOut(APIModel):
    id: int
    session_id: str
    event_type: str
    event_time: dt.datetime
    client_event_id: str | None
    ingestion_source: str
    source_adapter: str | None
    schema_version: str
    payload: dict[str, Any]
    idempotency_hit: bool = False


class AdaptationRequest(BaseModel):
    explicit_mood: str | None = None
    energy_level: float | None = Field(default=None, ge=0, le=1)
    heart_rate: int | None = Field(default=None, ge=25, le=220)
    hrv: float | None = Field(default=None, ge=0)
    noise_level_db: float | None = Field(default=None, ge=0)


class AdaptationOut(APIModel):
    id: int
    session_id: str
    decision_time: dt.datetime
    reason: str
    tempo_bpm: int
    guidance_intensity: str
    key_center: str
    adaptation_json: dict[str, Any]


class SessionEndRequest(BaseModel):
    user_value_rating: float | None = Field(default=None, ge=1, le=5)
    completed_goal: bool | None = None


class SessionEndOut(BaseModel):
    session: SessionOut
    summary: dict[str, Any]


class BhavEvaluateRequest(BaseModel):
    golden_profile: str = Field(default="maha_mantra_v1", min_length=1, max_length=40)
    lineage: str = Field(default="vaishnavism", min_length=1, max_length=60)
    persist: bool = True


class BhavEvaluationOut(APIModel):
    id: int | None = None
    session_id: str
    mantra_key: str | None
    lineage_id: str
    profile_name: str
    discipline: float
    resonance: float
    coherence: float
    composite: float
    passes_golden: bool
    detail_json: dict[str, Any]
    created_at: dt.datetime | None = None


class MahaMantraMetrics(BaseModel):
    duration_seconds: float = Field(ge=1, le=1800)
    voice_ratio_total: float = Field(ge=0, le=1)
    voice_ratio_student: float | None = Field(default=None, ge=0, le=1)
    voice_ratio_guru: float | None = Field(default=None, ge=0, le=1)
    pitch_stability: float = Field(ge=0, le=1)
    cadence_bpm: float = Field(ge=20, le=220)
    cadence_consistency: float = Field(ge=0, le=1)
    avg_energy: float = Field(ge=0, le=1)


class MahaMantraEvalRequest(BaseModel):
    stage: Literal["guided", "call_response", "independent"]
    lineage: str = Field(default="vaishnavism", min_length=1, max_length=60)
    golden_profile: str = Field(default="maha_mantra_v1", min_length=1, max_length=40)
    session_id: str | None = None
    metrics: MahaMantraMetrics


class MahaMantraEvalOut(BaseModel):
    stage: str
    lineage_id: str
    golden_profile: str
    discipline: float
    resonance: float
    coherence: float
    composite: float
    passes_golden: bool
    feedback: list[str]
    metrics_used: dict[str, Any]


class PartnerEventIn(BaseModel):
    session_id: str
    partner_source: str = Field(min_length=1, max_length=80)
    adapter_id: str = Field(min_length=1, max_length=80)
    event_type: str = Field(default="partner_signal", min_length=1, max_length=60)
    client_event_id: str | None = Field(default=None, max_length=120)
    schema_version: str = Field(default="v1", min_length=1, max_length=20)
    payload: dict[str, Any] = Field(default_factory=dict)


class WebhookSubscriptionCreate(BaseModel):
    target_url: str = Field(min_length=1, max_length=500)
    adapter_id: str = Field(min_length=1, max_length=80)
    event_types: list[str] = Field(default_factory=lambda: ["session_ended", "bhav_evaluated"])
    is_active: bool = True


class WebhookSubscriptionOut(APIModel):
    id: int
    target_url: str
    adapter_id: str
    event_types: list[str]
    is_active: bool
    created_at: dt.datetime


class EcosystemUsageOut(APIModel):
    date_key: str
    inbound_partner_events: int
    outbound_webhooks_queued: int
    exports_generated: int
    wearable_adapter_events: int
    content_export_events: int
    unique_partner_sources: int
    updated_at: dt.datetime


class BusinessSignalDailyOut(APIModel):
    date_key: str
    sessions_started: int
    sessions_completed: int
    meaningful_sessions: int
    avg_user_value_rating: float
    adaptation_helpful_rate: float
    day7_returning_users: int
    unique_active_users: int
    bhav_pass_rate: float
    updated_at: dt.datetime


class ExperimentCompareRequest(BaseModel):
    adaptive_values: list[float] = Field(min_length=2)
    static_values: list[float] = Field(min_length=2)


class ExperimentCompareOut(BaseModel):
    adaptive_mean: float
    static_mean: float
    uplift: float
    ci95_low: float
    ci95_high: float
    significant: bool


class ProgressOut(APIModel):
    user_id: str
    total_sessions: int
    completed_sessions: int
    total_practice_minutes: float
    avg_flow_score: float
    avg_pronunciation_score: float
    updated_at: dt.datetime


class HealthOut(BaseModel):
    ok: bool
    service: str
