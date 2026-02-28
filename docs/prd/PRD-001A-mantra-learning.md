# PRD-001A: Mantra Learning and Progression

- Parent: `PRD-001-platform.md`
- Status: Active
- Date: 2026-02-28

## Objective

Provide measurable progression in mantra practice quality through guided session loops and post-session learning signals.

## User Stories

- As a learner, I want pronunciation and cadence feedback so I can improve.
- As a learner, I want session summaries so I know what to practice next.
- As a practitioner, I want stage-based Maha Mantra evaluation to track readiness.

## Requirements

- Ingest `voice_window` events with cadence/pronunciation/flow signals.
- Generate adaptation guidance based on session context.
- Persist session summary metrics and user progress projections.
- Expose stage evaluation endpoint for guided/call-response/independent.

## Acceptance Criteria

- Pronunciation and flow metrics are present in session summary.
- `GET /v1/users/{user_id}/progress` reflects completed sessions.
- Maha Mantra stage evaluation returns composite and pass/fail.

## Metrics

- Avg pronunciation score trend
- Avg flow score trend
- Goal completion rate
- Meaningful session rate
