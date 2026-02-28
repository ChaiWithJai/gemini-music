# ADR 0001: DDIA Event Log + Projection Architecture

- Status: Accepted
- Date: 2026-02-28
- Decision owners: Product + API engineering

## Context

The product requires real-time adaptation and post-session analytics with strong replayability and idempotency guarantees. We need durable write-path facts and fast read-path views.

## Decision

Adopt an append-only event log (`session_events`) as the source of truth, with projection tables and summary models for read efficiency.

Implemented shape:

- Write model: `session_events`, `adaptation_decisions`, `bhav_evaluations`
- Read model: `sessions.summary_json`, `practice_progress`, `ecosystem_usage_daily`, `business_signal_daily`
- Recompute path: `scripts/recompute_projections.py`

## Consequences

Positive:

- Deterministic replay/backfill support
- Safer schema evolution via event contracts and projection recompute
- Better debugging and auditability

Tradeoffs:

- More moving parts than direct CRUD updates
- Projection consistency requires operational discipline

## Operational Guardrails

- Idempotency key on event ingestion (`client_event_id`)
- Contract checks in event payload validation
- Daily projection recompute and quality checks in CI/release gates
