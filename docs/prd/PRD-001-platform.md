# PRD-001: Gemini Music Platform (Retroactive Baseline)

- Status: Active
- Version: 1.0
- Date: 2026-02-28

## Problem Statement

Users need a real-time spiritual practice experience that teaches mantra quality and adapts in-session to context, instead of static playback.

## Product Goal

Deliver a real-time personalized mantra + AI-kirtan platform that adapts to listener input, optional biometrics, and environment context, while demonstrating measurable user and business signal.

## Primary Users

- Solo mantra learners
- Devotional practitioners using guided kirtan support
- Facilitators validating Bhav and progression quality

## In-Scope for This PRD

- Session lifecycle APIs
- Event ingestion and adaptation loop
- Bhav and Maha Mantra evaluation surfaces
- Scorecard and release evidence artifacts

## Out of Scope

- Native mobile production clients
- Medical/clinical biometric claims
- Multi-tenant enterprise admin features

## Success Metrics

- Scorecard total >= 85
- Demis lens >= 40 and Sundar lens >= 40
- Release gate status = PASS
- Goal scenario status = on track for hackathon demo

## Functional Requirements

- Start/end sessions and ingest idempotent live events
- Produce adaptation decisions with explainability payload
- Compute Bhav and lineage-based golden checks
- Export ecosystem and business daily projections
- Run evals and produce a single JSON status report for goal readiness

## Non-Functional Requirements

- Local and CI reproducibility with Python 3.13
- Deterministic fallback when Gemini path is unavailable
- Clear privacy defaults and consent controls

## Dependencies

- Gemini adapter configuration
- SQLAlchemy data layer and migrations
- GitHub Actions CI pipelines

## Sub-PRDs

- `PRD-001A-mantra-learning.md`
- `PRD-001B-ai-kirtan-adaptation.md`
- `PRD-001C-context-personalization-and-ecosystem.md`
