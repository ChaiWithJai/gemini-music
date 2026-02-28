# PRD-001B: AI-Kirtan Adaptation Behavior

- Parent: `PRD-001-platform.md`
- Status: Active
- Date: 2026-02-28

## Objective

Deliver real-time AI-assisted kirtan behavior that adjusts musical guidance and arrangement based on live context.

## User Stories

- As a practitioner, I want the accompaniment to match my current state.
- As a facilitator, I want explainable adaptation decisions for trust.
- As a learner, I want call-response support during practice.

## Requirements

- Adaptation endpoint returns tempo, key, guidance intensity, and explainability payload.
- Payload includes arrangement and coach action fields used by clients.
- Deterministic fallback path is available when Gemini call fails.

## Acceptance Criteria

- `POST /v1/sessions/{session_id}/adaptations` responds with structured payload.
- Adaptation differs when mood/biometric/environment context changes.
- Local POC supports staged learning flow with scoring.

## Metrics

- Adaptation helpful rate
- Session completion uplift vs baseline
- P95 adaptation latency in local eval chain
