from __future__ import annotations

import datetime as dt
from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    AdaptationDecision,
    BhavEvaluation,
    BusinessSignalDaily,
    EcosystemUsageDaily,
    IntegrationExportLog,
    PracticeProgress,
    SessionEvent,
    SessionModel,
    WebhookDelivery,
    WebhookSubscription,
)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _date_key(value: dt.datetime | dt.date) -> str:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value.isoformat()
    return value.date().isoformat()


def _upsert_ecosystem_row(db: Session, date_key: str) -> EcosystemUsageDaily:
    row = db.get(EcosystemUsageDaily, date_key)
    if row is None:
        row = EcosystemUsageDaily(date_key=date_key)
        savepoint = db.begin_nested()
        try:
            db.add(row)
            db.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            row = db.get(EcosystemUsageDaily, date_key)
            if row is None:
                raise
    return row


def _upsert_business_row(db: Session, date_key: str) -> BusinessSignalDaily:
    row = db.get(BusinessSignalDaily, date_key)
    if row is None:
        row = BusinessSignalDaily(date_key=date_key)
        savepoint = db.begin_nested()
        try:
            db.add(row)
            db.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            row = db.get(BusinessSignalDaily, date_key)
            if row is None:
                raise
    return row


def build_session_summary(
    db: Session,
    session: SessionModel,
    *,
    completed_goal_override: bool | None,
    user_value_rating: float | None,
) -> dict:
    events = db.scalars(
        select(SessionEvent).where(SessionEvent.session_id == session.id).order_by(SessionEvent.id.asc())
    ).all()
    decisions = db.scalars(
        select(AdaptationDecision)
        .where(AdaptationDecision.session_id == session.id)
        .order_by(AdaptationDecision.id.asc())
    ).all()

    flow_scores = [float(e.payload.get("flow_score")) for e in events if e.payload.get("flow_score") is not None]
    pronunciation_scores = [
        float(e.payload.get("pronunciation_score"))
        for e in events
        if e.payload.get("pronunciation_score") is not None
    ]

    helpful_flags = [
        1.0 if bool(e.payload.get("adaptation_helpful")) else 0.0
        for e in events
        if e.payload.get("adaptation_helpful") is not None
    ]

    practice_seconds = sum(float(e.payload.get("practice_seconds", 0.0)) for e in events)
    if practice_seconds <= 0:
        reference_end = session.ended_at or _utcnow()
        started_at = session.started_at
        if reference_end.tzinfo is not None:
            reference_end = reference_end.astimezone(dt.timezone.utc).replace(tzinfo=None)
        if started_at.tzinfo is not None:
            started_at = started_at.astimezone(dt.timezone.utc).replace(tzinfo=None)
        practice_seconds = max(0.0, (reference_end - started_at).total_seconds())

    practice_minutes = round(practice_seconds / 60.0, 2)
    target = max(1, session.target_duration_minutes)

    completed_goal = completed_goal_override
    if completed_goal is None:
        completed_goal = practice_minutes >= 0.8 * target

    avg_flow = round(mean(flow_scores), 3) if flow_scores else 0.0
    avg_pronunciation = round(mean(pronunciation_scores), 3) if pronunciation_scores else 0.0
    adaptation_helpful_rate = round(mean(helpful_flags), 3) if helpful_flags else 0.0

    meaningful_session = bool(
        practice_minutes >= 10 and completed_goal and (user_value_rating is None or user_value_rating >= 4.0)
    )

    return {
        "practice_minutes": practice_minutes,
        "events_count": len(events),
        "adaptations_count": len(decisions),
        "avg_flow_score": avg_flow,
        "avg_pronunciation_score": avg_pronunciation,
        "adaptation_helpful_rate": adaptation_helpful_rate,
        "completed_goal": completed_goal,
        "user_value_rating": user_value_rating,
        "meaningful_session": meaningful_session,
    }


def apply_progress_projection(db: Session, user_id: str, summary: dict) -> PracticeProgress:
    progress = db.get(PracticeProgress, user_id)
    if progress is None:
        progress = PracticeProgress(user_id=user_id)
        db.add(progress)
        db.flush()

    total_before = progress.total_sessions

    progress.total_sessions += 1
    progress.completed_sessions += 1 if summary.get("completed_goal") else 0
    progress.total_practice_minutes = round(
        progress.total_practice_minutes + float(summary.get("practice_minutes", 0.0)),
        2,
    )

    new_flow = float(summary.get("avg_flow_score", 0.0))
    new_pronunciation = float(summary.get("avg_pronunciation_score", 0.0))

    if total_before <= 0:
        progress.avg_flow_score = new_flow
        progress.avg_pronunciation_score = new_pronunciation
    else:
        progress.avg_flow_score = round(
            ((progress.avg_flow_score * total_before) + new_flow) / (total_before + 1),
            3,
        )
        progress.avg_pronunciation_score = round(
            ((progress.avg_pronunciation_score * total_before) + new_pronunciation) / (total_before + 1),
            3,
        )

    progress.updated_at = _utcnow()
    db.flush()
    return progress


def queue_webhook_deliveries(
    db: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    event_time: dt.datetime | None = None,
    max_attempts: int = 3,
) -> int:
    event_time = event_time or _utcnow()
    subscriptions = db.scalars(
        select(WebhookSubscription)
        .where(WebhookSubscription.is_active.is_(True))
        .order_by(WebhookSubscription.id.asc())
    ).all()

    queued = 0
    for sub in subscriptions:
        if event_type not in sub.event_types and "*" not in sub.event_types:
            continue
        db.add(
            WebhookDelivery(
                subscription_id=sub.id,
                event_type=event_type,
                payload=payload,
                status="queued",
                attempt_count=0,
                max_attempts=max(1, int(max_attempts)),
                next_attempt_at=event_time,
            )
        )
        queued += 1

    if queued:
        increment_ecosystem_usage(
            db,
            date_key=_date_key(event_time),
            outbound_webhooks_queued=queued,
        )
    return queued


def process_webhook_deliveries(
    db: Session,
    *,
    batch_size: int = 100,
    now: dt.datetime | None = None,
    ignore_schedule: bool = False,
    base_backoff_seconds: int = 5,
) -> dict[str, int]:
    now = now or _utcnow()
    query = (
        select(WebhookDelivery)
        .where(WebhookDelivery.status.in_(["queued", "retrying"]))
        .order_by(WebhookDelivery.id.asc())
        .limit(batch_size)
    )
    deliveries = db.scalars(query).all()

    processed = 0
    succeeded = 0
    retried = 0
    dead_lettered = 0
    failed_attempts = 0
    touched_dates: set[str] = set()

    for delivery in deliveries:
        if not ignore_schedule and delivery.next_attempt_at and delivery.next_attempt_at > now:
            continue

        processed += 1
        touched_dates.add(_date_key(delivery.created_at))
        subscription = db.get(WebhookSubscription, delivery.subscription_id) if delivery.subscription_id else None
        target_url = (subscription.target_url if subscription is not None else "").lower()
        force_fail = bool((delivery.payload or {}).get("force_webhook_fail"))
        should_fail = force_fail or ("fail" in target_url)

        if not should_fail:
            delivery.status = "delivered"
            delivery.delivered_at = now
            delivery.last_error = None
            succeeded += 1
            continue

        failed_attempts += 1
        delivery.attempt_count += 1
        delivery.last_error = "simulated_delivery_failure"
        if delivery.attempt_count >= max(1, int(delivery.max_attempts)):
            delivery.status = "dead_letter"
            delivery.dead_lettered_at = now
            delivery.dead_letter_reason = "max_attempts_exceeded"
            dead_lettered += 1
        else:
            backoff = max(1, int(base_backoff_seconds)) * (2 ** (delivery.attempt_count - 1))
            delivery.status = "retrying"
            delivery.next_attempt_at = now + dt.timedelta(seconds=backoff)
            retried += 1

    for date_key in touched_dates:
        refresh_ecosystem_usage_daily(db, date_key=date_key)

    db.flush()
    return {
        "processed": processed,
        "succeeded": succeeded,
        "retried": retried,
        "dead_lettered": dead_lettered,
        "failed_attempts": failed_attempts,
    }


def increment_ecosystem_usage(
    db: Session,
    *,
    date_key: str,
    inbound_partner_events: int = 0,
    outbound_webhooks_queued: int = 0,
    webhook_deliveries_succeeded: int = 0,
    webhook_deliveries_retrying: int = 0,
    webhook_dead_letters: int = 0,
    webhook_failed_attempts: int = 0,
    exports_generated: int = 0,
    wearable_adapter_events: int = 0,
    content_export_events: int = 0,
    unique_partner_sources: int | None = None,
) -> EcosystemUsageDaily:
    row = _upsert_ecosystem_row(db, date_key)
    row.inbound_partner_events += inbound_partner_events
    row.outbound_webhooks_queued += outbound_webhooks_queued
    row.webhook_deliveries_succeeded += webhook_deliveries_succeeded
    row.webhook_deliveries_retrying += webhook_deliveries_retrying
    row.webhook_dead_letters += webhook_dead_letters
    row.webhook_failed_attempts += webhook_failed_attempts
    row.exports_generated += exports_generated
    row.wearable_adapter_events += wearable_adapter_events
    row.content_export_events += content_export_events
    if unique_partner_sources is not None:
        row.unique_partner_sources = max(row.unique_partner_sources, unique_partner_sources)
    row.updated_at = _utcnow()
    db.flush()
    return row


def refresh_ecosystem_usage_daily(db: Session, *, date_key: str) -> EcosystemUsageDaily:
    row = _upsert_ecosystem_row(db, date_key)

    partner_events = db.scalars(
        select(SessionEvent)
        .where(func.date(SessionEvent.event_time) == date_key)
        .where(SessionEvent.ingestion_source.like("partner:%"))
    ).all()
    row.inbound_partner_events = len(partner_events)

    row.wearable_adapter_events = sum(
        1 for event in partner_events if (event.source_adapter or "").startswith("wearable_")
    )
    partner_content_events = sum(
        1 for event in partner_events if (event.source_adapter or "").startswith("content_")
    )
    row.unique_partner_sources = len({event.ingestion_source for event in partner_events})

    row.outbound_webhooks_queued = db.scalar(
        select(func.count(WebhookDelivery.id)).where(
            func.date(WebhookDelivery.created_at) == date_key,
            WebhookDelivery.status.in_(["queued", "retrying"]),
        )
    ) or 0
    row.webhook_deliveries_succeeded = db.scalar(
        select(func.count(WebhookDelivery.id)).where(
            func.date(WebhookDelivery.created_at) == date_key,
            WebhookDelivery.status == "delivered",
        )
    ) or 0
    row.webhook_deliveries_retrying = db.scalar(
        select(func.count(WebhookDelivery.id)).where(
            func.date(WebhookDelivery.created_at) == date_key,
            WebhookDelivery.status == "retrying",
        )
    ) or 0
    row.webhook_dead_letters = db.scalar(
        select(func.count(WebhookDelivery.id)).where(
            func.date(WebhookDelivery.created_at) == date_key,
            WebhookDelivery.status == "dead_letter",
        )
    ) or 0
    row.webhook_failed_attempts = db.scalar(
        select(func.coalesce(func.sum(WebhookDelivery.attempt_count), 0)).where(
            func.date(WebhookDelivery.created_at) == date_key
        )
    ) or 0

    export_logs = db.scalars(
        select(IntegrationExportLog).where(func.date(IntegrationExportLog.created_at) == date_key)
    ).all()
    row.exports_generated = len(export_logs)
    row.content_export_events = partner_content_events + sum(
        1 for log in export_logs if log.adapter_id.startswith("content_")
    )
    row.updated_at = _utcnow()
    db.flush()
    return row


def refresh_business_signal_daily(db: Session, *, date_key: str) -> BusinessSignalDaily:
    row = _upsert_business_row(db, date_key)

    started_sessions = db.scalars(
        select(SessionModel).where(func.date(SessionModel.started_at) == date_key)
    ).all()
    ended_sessions = db.scalars(
        select(SessionModel).where(
            SessionModel.ended_at.is_not(None),
            func.date(SessionModel.ended_at) == date_key,
        )
    ).all()

    row.sessions_started = len(started_sessions)
    row.sessions_completed = len(ended_sessions)
    row.unique_active_users = len({session.user_id for session in started_sessions})

    summary_payloads = [session.summary_json or {} for session in ended_sessions]
    row.meaningful_sessions = sum(
        1 for summary in summary_payloads if bool(summary.get("meaningful_session"))
    )

    ratings = [
        float(summary["user_value_rating"])
        for summary in summary_payloads
        if summary.get("user_value_rating") is not None
    ]
    row.avg_user_value_rating = round(mean(ratings), 3) if ratings else 0.0

    helpful_rates = [
        float(summary["adaptation_helpful_rate"])
        for summary in summary_payloads
        if summary.get("adaptation_helpful_rate") is not None
    ]
    row.adaptation_helpful_rate = round(mean(helpful_rates), 3) if helpful_rates else 0.0

    pass_flags = db.scalars(
        select(BhavEvaluation.passes_golden).where(
            func.date(BhavEvaluation.created_at) == date_key
        )
    ).all()
    if pass_flags:
        row.bhav_pass_rate = round(sum(1.0 if flag else 0.0 for flag in pass_flags) / len(pass_flags), 3)
    else:
        row.bhav_pass_rate = 0.0

    threshold_date = dt.date.fromisoformat(date_key) - dt.timedelta(days=7)
    users_started_today = {session.user_id for session in started_sessions}
    day7_returning = 0
    if users_started_today:
        historical_rows = db.execute(
            select(SessionModel.user_id, SessionModel.started_at).where(
                SessionModel.user_id.in_(users_started_today)
            )
        ).all()
        # SQLAlchemy typed tuple returns list of Row; use per-user earliest historical.
        user_to_oldest: dict[str, dt.datetime] = {}
        for user_id, started_at in historical_rows:
            if user_id not in user_to_oldest or started_at < user_to_oldest[user_id]:
                user_to_oldest[user_id] = started_at
        for user_id in users_started_today:
            oldest = user_to_oldest.get(user_id)
            if oldest and oldest.date() <= threshold_date:
                day7_returning += 1
    row.day7_returning_users = day7_returning

    row.updated_at = _utcnow()
    db.flush()
    return row


def refresh_daily_projections(db: Session, *, date_key: str) -> tuple[EcosystemUsageDaily, BusinessSignalDaily]:
    eco = refresh_ecosystem_usage_daily(db, date_key=date_key)
    biz = refresh_business_signal_daily(db, date_key=date_key)
    return eco, biz


def recompute_all_daily_projections(db: Session) -> dict[str, int]:
    date_keys: set[str] = set()

    session_started_keys = db.scalars(select(func.date(SessionModel.started_at))).all()
    session_ended_keys = db.scalars(select(func.date(SessionModel.ended_at)).where(SessionModel.ended_at.is_not(None))).all()
    event_keys = db.scalars(select(func.date(SessionEvent.event_time))).all()
    bhav_keys = db.scalars(select(func.date(BhavEvaluation.created_at))).all()
    webhook_keys = db.scalars(select(func.date(WebhookDelivery.created_at))).all()
    export_keys = db.scalars(select(func.date(IntegrationExportLog.created_at))).all()

    for key in [*session_started_keys, *session_ended_keys, *event_keys, *bhav_keys, *webhook_keys, *export_keys]:
        if key:
            date_keys.add(str(key))

    for key in sorted(date_keys):
        refresh_daily_projections(db, date_key=key)

    db.flush()
    return {"days_recomputed": len(date_keys)}


def compute_business_cohorts(db: Session) -> dict[str, Any]:
    sessions = db.scalars(
        select(SessionModel).order_by(SessionModel.started_at.asc())
    ).all()
    by_day: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"users": set(), "sessions": 0, "completed": 0, "meaningful": 0}
    )
    for session in sessions:
        key = _date_key(session.started_at)
        bucket = by_day[key]
        bucket["users"].add(session.user_id)
        bucket["sessions"] += 1
        if session.summary_json and session.summary_json.get("completed_goal"):
            bucket["completed"] += 1
        if session.summary_json and session.summary_json.get("meaningful_session"):
            bucket["meaningful"] += 1

    rows: list[dict[str, Any]] = []
    for key in sorted(by_day):
        bucket = by_day[key]
        sessions_count = max(1, bucket["sessions"])
        rows.append(
            {
                "date_key": key,
                "active_users": len(bucket["users"]),
                "sessions": bucket["sessions"],
                "completion_rate": round(bucket["completed"] / sessions_count, 3),
                "meaningful_rate": round(bucket["meaningful"] / sessions_count, 3),
            }
        )

    return {
        "rows": rows,
        "days": len(rows),
    }
