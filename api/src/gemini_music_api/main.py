from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Connection, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .db import Base, engine, get_db
from .models import (
    AdaptationDecision,
    AudioChunk,
    BusinessSignalDaily,
    ConsentRecord,
    EcosystemUsageDaily,
    IntegrationExportLog,
    SessionEvent,
    SessionModel,
    StageScoreProjection,
    User,
    WebhookSubscription,
)
from .schemas import (
    AdaptationOut,
    AdaptationRequest,
    AudioChunkIn,
    AudioChunkIngestOut,
    BhavEvaluateRequest,
    BhavEvaluationOut,
    BusinessSignalDailyOut,
    ConsentOut,
    ConsentUpdate,
    EcosystemUsageOut,
    ExperimentCompareOut,
    ExperimentCompareRequest,
    HealthOut,
    MahaTimingOut,
    MahaMantraEvalOut,
    MahaMantraEvalRequest,
    PartnerEventIn,
    ProgressOut,
    SessionEndOut,
    SessionEndRequest,
    SessionEventIn,
    SessionEventOut,
    SessionOut,
    SessionStartRequest,
    UserCreate,
    UserOut,
    WebhookSubscriptionCreate,
    WebhookSubscriptionOut,
    StageScoreProjectionOut,
)
from .services.adaptation import AdaptationContext, generate_adaptation
from .services.audio_scoring import normalize_audio_chunk, recompute_stage_projection
from .services.ai_kirtan_contract import quality_rubric_score, verify_payload_contract
from .services.bhav import DEFAULT_GOLDEN_PROFILE, compute_bhav, resolve_lineage
from .services.event_contracts import validate_event_payload
from .services.experiments import compare_adaptive_vs_static
from .services.gemini_adapter import try_gemini_adaptation
from .services.maha_mantra_timing import load_maha_mantra_timing_markers
from .services.maha_mantra_eval import evaluate_maha_mantra_stage
from .services.projections import (
    apply_progress_projection,
    build_session_summary,
    compute_business_cohorts,
    increment_ecosystem_usage,
    process_webhook_deliveries,
    queue_webhook_deliveries,
    recompute_all_daily_projections,
    refresh_daily_projections,
)

app = FastAPI(
    title="Gemini Music API",
    version="0.1.0",
    description=(
        "Core data and API layer for real-time mantra learning + AI-assisted kirtan. "
        "Design: append-only session event log + projected session/progress views."
    ),
)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DEMO_WEB_DIR = Path(__file__).resolve().parents[2] / "web-demo"
if WEB_DIR.exists():
    app.mount("/poc", StaticFiles(directory=str(WEB_DIR), html=True), name="poc")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> RedirectResponse:
        return RedirectResponse(url="/poc/favicon.svg")

if DEMO_WEB_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(DEMO_WEB_DIR), html=True), name="demo")


def _sqlite_table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).first()
    return row is not None


def _sqlite_table_columns(conn: Connection, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").all()
    # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
    return {str(r[1]) for r in rows}


def _apply_sqlite_compat_migrations() -> None:
    """
    Lightweight compatibility migrations for local hackathon SQLite files.
    """
    with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return

        if _sqlite_table_exists(conn, "session_events"):
            cols = _sqlite_table_columns(conn, "session_events")
            if "source_adapter" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE session_events ADD COLUMN source_adapter VARCHAR(80)"
                )
            if "schema_version" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE session_events ADD COLUMN schema_version VARCHAR(20) NOT NULL DEFAULT 'v1'"
                )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_session_events_source_adapter ON session_events (source_adapter)"
            )

        if _sqlite_table_exists(conn, "webhook_deliveries"):
            cols = _sqlite_table_columns(conn, "webhook_deliveries")
            if "attempt_count" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
                )
            if "max_attempts" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3"
                )
            if "next_attempt_at" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN next_attempt_at DATETIME"
                )
            if "delivered_at" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN delivered_at DATETIME"
                )
            if "dead_lettered_at" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN dead_lettered_at DATETIME"
                )
            if "last_error" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN last_error VARCHAR(500)"
                )
            if "dead_letter_reason" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE webhook_deliveries ADD COLUMN dead_letter_reason VARCHAR(500)"
                )

        if _sqlite_table_exists(conn, "ecosystem_usage_daily"):
            cols = _sqlite_table_columns(conn, "ecosystem_usage_daily")
            if "webhook_deliveries_succeeded" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE ecosystem_usage_daily ADD COLUMN webhook_deliveries_succeeded INTEGER NOT NULL DEFAULT 0"
                )
            if "webhook_deliveries_retrying" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE ecosystem_usage_daily ADD COLUMN webhook_deliveries_retrying INTEGER NOT NULL DEFAULT 0"
                )
            if "webhook_dead_letters" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE ecosystem_usage_daily ADD COLUMN webhook_dead_letters INTEGER NOT NULL DEFAULT 0"
                )
            if "webhook_failed_attempts" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE ecosystem_usage_daily ADD COLUMN webhook_failed_attempts INTEGER NOT NULL DEFAULT 0"
                )


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_compat_migrations()


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _date_key(value: dt.datetime | dt.date) -> str:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value.isoformat()
    return value.date().isoformat()


def _north_star_value(row: BusinessSignalDaily | None) -> float:
    if row is None:
        return 0.0
    started = max(1, int(row.sessions_started))
    meaningful_rate = float(row.meaningful_sessions) / float(started)
    value = meaningful_rate * float(row.adaptation_helpful_rate) * float(row.bhav_pass_rate)
    return round(max(0.0, min(1.0, value)), 4)


def _must_get_user(db: DBSession, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _must_get_session(db: DBSession, session_id: str) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _latest_consent(db: DBSession, user_id: str) -> ConsentRecord | None:
    return db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id)
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .limit(1)
    ).first()


def _ingest_event_row(
    db: DBSession,
    *,
    session: SessionModel,
    event_type: str,
    client_event_id: str | None,
    payload: dict,
    ingestion_source: str,
    source_adapter: str | None,
    schema_version: str,
) -> SessionEventOut:
    if session.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    validate_event_payload(
        event_type=event_type,
        payload=payload,
        schema_version=schema_version,
    )

    if client_event_id:
        existing = db.scalars(
            select(SessionEvent).where(
                SessionEvent.session_id == session.id,
                SessionEvent.client_event_id == client_event_id,
            )
        ).first()
        if existing:
            out = SessionEventOut.model_validate(existing)
            out.idempotency_hit = True
            return out

    event = SessionEvent(
        session_id=session.id,
        event_type=event_type,
        client_event_id=client_event_id,
        ingestion_source=ingestion_source,
        source_adapter=source_adapter,
        schema_version=schema_version,
        payload=payload,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if client_event_id:
            existing = db.scalars(
                select(SessionEvent).where(
                    SessionEvent.session_id == session.id,
                    SessionEvent.client_event_id == client_event_id,
                )
            ).first()
            if existing:
                out = SessionEventOut.model_validate(existing)
                out.idempotency_hit = True
                return out
        raise

    db.refresh(event)
    out = SessionEventOut.model_validate(event)
    out.idempotency_hit = False
    return out


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(ok=True, service="gemini-music-api")


@app.post("/v1/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Annotated[DBSession, Depends(get_db)]) -> User:
    user = User(display_name=payload.display_name.strip())
    db.add(user)
    db.flush()

    consent = ConsentRecord(user_id=user.id)
    db.add(consent)
    db.commit()
    db.refresh(user)
    return user


@app.put("/v1/users/{user_id}/consent", response_model=ConsentOut)
def set_user_consent(
    user_id: str,
    payload: ConsentUpdate,
    db: Annotated[DBSession, Depends(get_db)],
) -> ConsentRecord:
    _must_get_user(db, user_id)
    consent = ConsentRecord(
        user_id=user_id,
        biometric_enabled=payload.biometric_enabled,
        environmental_enabled=payload.environmental_enabled,
        raw_audio_storage_enabled=payload.raw_audio_storage_enabled,
        policy_version=payload.policy_version,
        source="api",
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


@app.get("/v1/users/{user_id}/consent", response_model=ConsentOut)
def get_user_consent(user_id: str, db: Annotated[DBSession, Depends(get_db)]) -> ConsentRecord:
    _must_get_user(db, user_id)
    consent = _latest_consent(db, user_id)
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")
    return consent


@app.post("/v1/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(payload: SessionStartRequest, db: Annotated[DBSession, Depends(get_db)]) -> SessionModel:
    _must_get_user(db, payload.user_id)

    session = SessionModel(
        user_id=payload.user_id,
        intention=payload.intention,
        mantra_key=payload.mantra_key,
        mood=payload.mood,
        target_duration_minutes=payload.target_duration_minutes,
        status="ACTIVE",
    )
    db.add(session)
    db.flush()

    session_started = SessionEvent(
        session_id=session.id,
        event_type="session_started",
        client_event_id=f"session_start:{session.id}",
        schema_version="v1",
        payload={
            "intention": payload.intention,
            "mood": payload.mood,
            "mantra_key": payload.mantra_key,
            "target_duration_minutes": payload.target_duration_minutes,
        },
    )
    db.add(session_started)

    db.commit()
    refresh_daily_projections(db, date_key=_date_key(session.started_at))
    db.commit()
    db.refresh(session)
    return session


@app.get("/v1/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Annotated[DBSession, Depends(get_db)]) -> SessionModel:
    return _must_get_session(db, session_id)


@app.post("/v1/sessions/{session_id}/events", response_model=SessionEventOut, status_code=status.HTTP_201_CREATED)
def ingest_session_event(
    session_id: str,
    payload: SessionEventIn,
    db: Annotated[DBSession, Depends(get_db)],
) -> SessionEventOut:
    session = _must_get_session(db, session_id)
    out = _ingest_event_row(
        db,
        session=session,
        event_type=payload.event_type,
        client_event_id=payload.client_event_id,
        payload=payload.payload,
        ingestion_source="api",
        source_adapter=payload.source_adapter,
        schema_version=payload.schema_version,
    )
    refresh_daily_projections(db, date_key=_date_key(out.event_time))
    db.commit()
    return out


@app.post("/v1/sessions/{session_id}/adaptations", response_model=AdaptationOut)
def create_adaptation(
    session_id: str,
    payload: AdaptationRequest,
    db: Annotated[DBSession, Depends(get_db)],
) -> AdaptationDecision:
    session = _must_get_session(db, session_id)
    if session.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    latest_signal = db.scalars(
        select(SessionEvent)
        .where(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.id.desc())
        .limit(1)
    ).first()

    p = latest_signal.payload if latest_signal else {}

    ctx = AdaptationContext(
        mood=payload.explicit_mood or session.mood,
        cadence_bpm=float(p.get("cadence_bpm")) if p.get("cadence_bpm") is not None else None,
        pronunciation_score=(
            float(p.get("pronunciation_score")) if p.get("pronunciation_score") is not None else None
        ),
        flow_score=float(p.get("flow_score")) if p.get("flow_score") is not None else None,
        heart_rate=payload.heart_rate if payload.heart_rate is not None else p.get("heart_rate"),
        noise_level_db=(
            payload.noise_level_db if payload.noise_level_db is not None else p.get("noise_level_db")
        ),
    )

    gemini_error: str | None = None
    try:
        gemini_payload = try_gemini_adaptation(
            context={
                "mood": ctx.mood,
                "cadence_bpm": ctx.cadence_bpm,
                "pronunciation_score": ctx.pronunciation_score,
                "flow_score": ctx.flow_score,
                "heart_rate": ctx.heart_rate,
                "noise_level_db": ctx.noise_level_db,
                "session_id": session_id,
                "mantra_key": session.mantra_key,
            }
        )
    except Exception as exc:  # noqa: BLE001
        gemini_payload = None
        gemini_error = str(exc)
    decision_payload = gemini_payload if gemini_payload is not None else generate_adaptation(ctx)
    if gemini_error:
        decision_payload.setdefault("adaptation_json", {}).setdefault("fallback", {})["reason"] = (
            f"gemini_transient_error:{gemini_error}"
        )
    contract_ok, contract_errors = verify_payload_contract(decision_payload)
    if not contract_ok:
        decision_payload = generate_adaptation(ctx)
        decision_payload.setdefault("adaptation_json", {}).setdefault("contract", {})["fallback_from_invalid_payload"] = True
        decision_payload["adaptation_json"]["contract"]["errors"] = contract_errors
    decision_payload.setdefault("adaptation_json", {}).setdefault("contract", {})["quality_score"] = round(
        quality_rubric_score(decision_payload),
        3,
    )
    decision = AdaptationDecision(
        session_id=session_id,
        reason=decision_payload["reason"],
        tempo_bpm=decision_payload["tempo_bpm"],
        guidance_intensity=decision_payload["guidance_intensity"],
        key_center=decision_payload["key_center"],
        adaptation_json=decision_payload["adaptation_json"],
    )
    db.add(decision)

    event = SessionEvent(
        session_id=session_id,
        event_type="adaptation_applied",
        schema_version="v1",
        payload={
            "tempo_bpm": decision.tempo_bpm,
            "guidance_intensity": decision.guidance_intensity,
            "key_center": decision.key_center,
        },
    )
    db.add(event)

    db.commit()
    queue_webhook_deliveries(
        db,
        event_type="adaptation_applied",
        payload={
            "session_id": session_id,
            "tempo_bpm": decision.tempo_bpm,
            "guidance_intensity": decision.guidance_intensity,
        },
    )
    refresh_daily_projections(db, date_key=_date_key(decision.decision_time))
    db.commit()
    db.refresh(decision)
    return decision


@app.post("/v1/sessions/{session_id}/end", response_model=SessionEndOut)
def end_session(
    session_id: str,
    payload: SessionEndRequest,
    db: Annotated[DBSession, Depends(get_db)],
) -> SessionEndOut:
    session = _must_get_session(db, session_id)
    if session.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already ended")

    session.ended_at = _utcnow()
    session.status = "ENDED"

    summary = build_session_summary(
        db,
        session,
        completed_goal_override=payload.completed_goal,
        user_value_rating=payload.user_value_rating,
    )
    session.summary_json = summary

    apply_progress_projection(db, session.user_id, summary)

    end_event = SessionEvent(
        session_id=session.id,
        event_type="session_ended",
        schema_version="v1",
        payload={
            "summary": summary,
        },
    )
    db.add(end_event)

    db.commit()
    queue_webhook_deliveries(
        db,
        event_type="session_ended",
        payload={
            "session_id": session.id,
            "user_id": session.user_id,
            "summary": summary,
        },
    )
    refresh_daily_projections(db, date_key=_date_key(session.ended_at or _utcnow()))
    db.commit()
    db.refresh(session)
    return SessionEndOut(session=SessionOut.model_validate(session), summary=summary)


@app.post("/v1/sessions/{session_id}/bhav", response_model=BhavEvaluationOut)
def evaluate_bhav(
    session_id: str,
    payload: BhavEvaluateRequest,
    db: Annotated[DBSession, Depends(get_db)],
) -> BhavEvaluationOut:
    from .models import BhavEvaluation

    session = _must_get_session(db, session_id)
    if session.status != "ENDED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session must be ended before Bhav evaluation",
        )

    summary = session.summary_json
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Session summary missing; end session first",
        )

    events = db.scalars(
        select(SessionEvent)
        .where(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.id.asc())
    ).all()

    if payload.golden_profile != DEFAULT_GOLDEN_PROFILE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported golden profile: {payload.golden_profile}",
        )

    try:
        lineage = resolve_lineage(payload.lineage)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    bhav = compute_bhav(
        mantra_key=session.mantra_key,
        target_duration_minutes=session.target_duration_minutes,
        summary=summary,
        event_payloads=[e.payload for e in events],
        lineage=lineage,
        golden_profile=payload.golden_profile,
    )

    if payload.persist:
        row = BhavEvaluation(
            session_id=session.id,
            mantra_key=session.mantra_key,
            lineage_id=lineage.id,
            profile_name=payload.golden_profile,
            discipline=bhav["discipline"],
            resonance=bhav["resonance"],
            coherence=bhav["coherence"],
            composite=bhav["composite"],
            passes_golden=bhav["passes_golden"],
            detail_json=bhav["detail_json"],
        )
        db.add(row)
        db.commit()
        queue_webhook_deliveries(
            db,
            event_type="bhav_evaluated",
            payload={
                "session_id": session.id,
                "lineage_id": lineage.id,
                "composite": bhav["composite"],
                "passes_golden": bhav["passes_golden"],
            },
        )
        refresh_daily_projections(db, date_key=_date_key(_utcnow()))
        db.commit()
        db.refresh(row)
        return BhavEvaluationOut.model_validate(row)

    return BhavEvaluationOut(
        id=None,
        session_id=session.id,
        mantra_key=session.mantra_key,
        lineage_id=lineage.id,
        profile_name=payload.golden_profile,
        discipline=bhav["discipline"],
        resonance=bhav["resonance"],
        coherence=bhav["coherence"],
        composite=bhav["composite"],
        passes_golden=bhav["passes_golden"],
        detail_json=bhav["detail_json"],
        created_at=None,
    )


@app.get("/v1/maha-mantra/timing", response_model=MahaTimingOut)
def get_maha_mantra_timing() -> MahaTimingOut:
    return MahaTimingOut.model_validate(load_maha_mantra_timing_markers())


@app.post("/v1/maha-mantra/evaluate", response_model=MahaMantraEvalOut)
def evaluate_maha_mantra(payload: MahaMantraEvalRequest) -> MahaMantraEvalOut:
    if payload.golden_profile != DEFAULT_GOLDEN_PROFILE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported golden profile: {payload.golden_profile}",
        )

    try:
        lineage = resolve_lineage(payload.lineage)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return evaluate_maha_mantra_stage(
        stage=payload.stage,
        metrics=payload.metrics,
        lineage=lineage,
        golden_profile=payload.golden_profile,
    )


@app.post(
    "/v1/sessions/{session_id}/audio/chunks",
    response_model=AudioChunkIngestOut,
    status_code=status.HTTP_201_CREATED,
)
def ingest_audio_chunk(
    session_id: str,
    payload: AudioChunkIn,
    db: Annotated[DBSession, Depends(get_db)],
) -> AudioChunkIngestOut:
    session = _must_get_session(db, session_id)
    if session.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")
    if payload.golden_profile != DEFAULT_GOLDEN_PROFILE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported golden profile: {payload.golden_profile}",
        )

    try:
        lineage = resolve_lineage(payload.lineage)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    existing = db.scalars(
        select(AudioChunk).where(
            AudioChunk.session_id == session_id,
            AudioChunk.chunk_id == payload.chunk_id,
        )
    ).first()
    if existing is not None:
        projection = db.scalars(
            select(StageScoreProjection).where(
                StageScoreProjection.session_id == session_id,
                StageScoreProjection.stage == existing.stage,
                StageScoreProjection.lineage_id == existing.lineage_id,
                StageScoreProjection.golden_profile == existing.golden_profile,
            )
        ).first()
        if projection is None:
            projection = recompute_stage_projection(
                db,
                session_id=session_id,
                stage=existing.stage,
                lineage_id=existing.lineage_id,
                golden_profile=existing.golden_profile,
            )
            db.commit()
            db.refresh(projection)

        out = AudioChunkIngestOut.model_validate(existing)
        out.idempotency_hit = True
        out.projection = StageScoreProjectionOut.model_validate(projection)
        return out

    features_json, metrics_json, chunk_confidence = normalize_audio_chunk(
        t_start_ms=payload.t_start_ms,
        t_end_ms=payload.t_end_ms,
        features=payload.features,
    )
    row = AudioChunk(
        session_id=session_id,
        stage=payload.stage,
        round_index=payload.round_index,
        chunk_id=payload.chunk_id,
        seq=payload.seq,
        t_start_ms=payload.t_start_ms,
        t_end_ms=payload.t_end_ms,
        sample_rate_hz=payload.sample_rate_hz,
        encoding=payload.encoding,
        blob_uri=payload.blob_uri,
        lineage_id=lineage.id,
        golden_profile=payload.golden_profile,
        features_json=features_json,
        metrics_json=metrics_json,
        confidence=chunk_confidence,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing_after_conflict = db.scalars(
            select(AudioChunk).where(
                AudioChunk.session_id == session_id,
                AudioChunk.chunk_id == payload.chunk_id,
            )
        ).first()
        if existing_after_conflict is None:
            raise
        projection = db.scalars(
            select(StageScoreProjection).where(
                StageScoreProjection.session_id == session_id,
                StageScoreProjection.stage == existing_after_conflict.stage,
                StageScoreProjection.lineage_id == existing_after_conflict.lineage_id,
                StageScoreProjection.golden_profile == existing_after_conflict.golden_profile,
            )
        ).first()
        if projection is None:
            projection = recompute_stage_projection(
                db,
                session_id=session_id,
                stage=existing_after_conflict.stage,
                lineage_id=existing_after_conflict.lineage_id,
                golden_profile=existing_after_conflict.golden_profile,
            )
            db.commit()
            db.refresh(projection)

        out = AudioChunkIngestOut.model_validate(existing_after_conflict)
        out.idempotency_hit = True
        out.projection = StageScoreProjectionOut.model_validate(projection)
        return out

    projection = recompute_stage_projection(
        db,
        session_id=session_id,
        stage=payload.stage,
        lineage_id=lineage.id,
        golden_profile=payload.golden_profile,
    )
    db.add(
        SessionEvent(
            session_id=session_id,
            event_type="audio_chunk_ingested",
            client_event_id=f"audio_chunk:{payload.chunk_id}",
            schema_version="v1",
            payload={
                "stage": payload.stage,
                "chunk_id": payload.chunk_id,
                "round_index": payload.round_index,
                "metrics": metrics_json,
                "projection": {
                    "discipline": projection.discipline,
                    "resonance": projection.resonance,
                    "coherence": projection.coherence,
                    "composite": projection.composite,
                    "confidence": projection.confidence,
                },
            },
        )
    )
    refresh_daily_projections(db, date_key=_date_key(row.ingested_at))
    db.commit()

    db.refresh(row)
    db.refresh(projection)
    out = AudioChunkIngestOut.model_validate(row)
    out.idempotency_hit = False
    out.projection = StageScoreProjectionOut.model_validate(projection)
    return out


@app.get(
    "/v1/sessions/{session_id}/stage-projections",
    response_model=list[StageScoreProjectionOut],
)
def list_stage_projections(
    session_id: str,
    db: Annotated[DBSession, Depends(get_db)],
) -> list[StageScoreProjection]:
    _must_get_session(db, session_id)
    rows = db.scalars(
        select(StageScoreProjection)
        .where(StageScoreProjection.session_id == session_id)
        .order_by(StageScoreProjection.updated_at.desc(), StageScoreProjection.id.desc())
    ).all()

    stage_rank = {
        "guided": 0,
        "call_response": 1,
        "independent": 2,
    }
    rows.sort(key=lambda row: (stage_rank.get(row.stage, 99), row.id))
    return rows


@app.post("/v1/integrations/events", response_model=SessionEventOut, status_code=status.HTTP_201_CREATED)
def ingest_partner_event(
    payload: PartnerEventIn,
    db: Annotated[DBSession, Depends(get_db)],
) -> SessionEventOut:
    session = _must_get_session(db, payload.session_id)
    out = _ingest_event_row(
        db,
        session=session,
        event_type=payload.event_type,
        client_event_id=payload.client_event_id,
        payload=payload.payload,
        ingestion_source=f"partner:{payload.partner_source}",
        source_adapter=payload.adapter_id,
        schema_version=payload.schema_version,
    )

    increment_ecosystem_usage(
        db,
        date_key=_date_key(out.event_time),
        inbound_partner_events=1,
        wearable_adapter_events=1 if payload.adapter_id.startswith("wearable_") else 0,
        content_export_events=1 if payload.adapter_id.startswith("content_") else 0,
    )
    refresh_daily_projections(db, date_key=_date_key(out.event_time))
    db.commit()
    return out


@app.post("/v1/integrations/webhooks", response_model=WebhookSubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_webhook_subscription(
    payload: WebhookSubscriptionCreate,
    db: Annotated[DBSession, Depends(get_db)],
) -> WebhookSubscription:
    subscription = WebhookSubscription(
        target_url=payload.target_url.strip(),
        adapter_id=payload.adapter_id.strip(),
        event_types=payload.event_types,
        is_active=payload.is_active,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@app.get("/v1/integrations/webhooks", response_model=list[WebhookSubscriptionOut])
def list_webhook_subscriptions(db: Annotated[DBSession, Depends(get_db)]) -> list[WebhookSubscription]:
    return db.scalars(
        select(WebhookSubscription).order_by(WebhookSubscription.id.asc())
    ).all()


@app.get("/v1/integrations/exports/business-signals/daily", response_model=BusinessSignalDailyOut)
def export_business_signals_daily(
    db: Annotated[DBSession, Depends(get_db)],
    date_key: str | None = None,
) -> BusinessSignalDaily:
    if date_key:
        refresh_daily_projections(db, date_key=date_key)
        row = db.get(BusinessSignalDaily, date_key)
    else:
        row = db.scalars(
            select(BusinessSignalDaily).order_by(BusinessSignalDaily.date_key.desc())
        ).first()
        if row is not None:
            refresh_daily_projections(db, date_key=row.date_key)
            row = db.get(BusinessSignalDaily, row.date_key)

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business signals available")

    export_log = IntegrationExportLog(
        export_type="business_signals_daily",
        adapter_id="content_partner_export",
        payload={"date_key": row.date_key},
    )
    db.add(export_log)
    increment_ecosystem_usage(
        db,
        date_key=row.date_key,
        exports_generated=1,
        content_export_events=1,
    )
    refresh_daily_projections(db, date_key=row.date_key)
    db.commit()
    db.refresh(row)
    return row


@app.get("/v1/integrations/exports/ecosystem-usage/daily", response_model=EcosystemUsageOut)
def export_ecosystem_usage_daily(
    db: Annotated[DBSession, Depends(get_db)],
    date_key: str | None = None,
) -> EcosystemUsageDaily:
    if date_key:
        refresh_daily_projections(db, date_key=date_key)
        row = db.get(EcosystemUsageDaily, date_key)
    else:
        row = db.scalars(
            select(EcosystemUsageDaily).order_by(EcosystemUsageDaily.date_key.desc())
        ).first()
        if row is not None:
            refresh_daily_projections(db, date_key=row.date_key)
            row = db.get(EcosystemUsageDaily, row.date_key)

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No ecosystem usage data available")
    db.commit()
    db.refresh(row)
    return row


@app.post("/v1/analytics/experiments/adaptive-vs-static", response_model=ExperimentCompareOut)
def experiment_adaptive_vs_static(payload: ExperimentCompareRequest) -> ExperimentCompareOut:
    result = compare_adaptive_vs_static(
        adaptive_values=[float(v) for v in payload.adaptive_values],
        static_values=[float(v) for v in payload.static_values],
    )
    return ExperimentCompareOut(**result)


@app.get("/v1/analytics/business-cohorts")
def get_business_cohorts(db: Annotated[DBSession, Depends(get_db)]) -> dict:
    return compute_business_cohorts(db)


@app.get("/v1/analytics/business-signal/north-star")
def get_north_star_metric(db: Annotated[DBSession, Depends(get_db)]) -> dict:
    row = db.scalars(
        select(BusinessSignalDaily).order_by(BusinessSignalDaily.date_key.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business signals available")

    contract_path = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "north_star_metric.v1.json"
    contract: dict = {}
    if contract_path.exists():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))

    started = max(1, int(row.sessions_started))
    components = {
        "meaningful_session_rate": round(float(row.meaningful_sessions) / float(started), 4),
        "adaptation_helpful_rate": round(float(row.adaptation_helpful_rate), 4),
        "bhav_pass_rate": round(float(row.bhav_pass_rate), 4),
    }
    return {
        "date_key": row.date_key,
        "metric_id": contract.get("metric_id", "NSM-001"),
        "version": contract.get("version", "1.0.0"),
        "value": _north_star_value(row),
        "components": components,
        "formula": contract.get("formula"),
    }


@app.get("/v1/analytics/business-signal/attribution")
def get_business_signal_attribution(db: Annotated[DBSession, Depends(get_db)]) -> dict:
    rows = db.scalars(
        select(BusinessSignalDaily).order_by(BusinessSignalDaily.date_key.desc()).limit(7)
    ).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business signals available")

    ordered = list(reversed(rows))
    timeline = []
    for row in ordered:
        started = max(1, int(row.sessions_started))
        meaningful_rate = round(float(row.meaningful_sessions) / float(started), 4)
        timeline.append(
            {
                "date_key": row.date_key,
                "sessions_started": row.sessions_started,
                "sessions_completed": row.sessions_completed,
                "meaningful_sessions": row.meaningful_sessions,
                "meaningful_session_rate": meaningful_rate,
                "day7_returning_users": row.day7_returning_users,
                "north_star_value": _north_star_value(row),
            }
        )

    first = timeline[0]
    last = timeline[-1]
    return {
        "window_days": len(timeline),
        "timeline": timeline,
        "trend": {
            "meaningful_session_rate_delta": round(
                float(last["meaningful_session_rate"]) - float(first["meaningful_session_rate"]),
                4,
            ),
            "day7_returning_users_delta": int(last["day7_returning_users"]) - int(first["day7_returning_users"]),
            "north_star_delta": round(
                float(last["north_star_value"]) - float(first["north_star_value"]),
                4,
            ),
        },
    }


@app.post("/v1/admin/webhooks/process")
def process_webhooks(
    db: Annotated[DBSession, Depends(get_db)],
    batch_size: int = 100,
    ignore_schedule: bool = False,
) -> dict:
    result = process_webhook_deliveries(
        db,
        batch_size=max(1, min(batch_size, 1000)),
        ignore_schedule=ignore_schedule,
    )
    db.commit()
    return result


@app.post("/v1/admin/projections/recompute")
def recompute_projections(db: Annotated[DBSession, Depends(get_db)]) -> dict:
    result = recompute_all_daily_projections(db)
    db.commit()
    return result


@app.get("/v1/users/{user_id}/progress", response_model=ProgressOut)
def get_user_progress(user_id: str, db: Annotated[DBSession, Depends(get_db)]) -> ProgressOut:
    _must_get_user(db, user_id)
    from .models import PracticeProgress

    progress = db.get(PracticeProgress, user_id)
    if progress is None:
        progress = PracticeProgress(user_id=user_id)
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress
