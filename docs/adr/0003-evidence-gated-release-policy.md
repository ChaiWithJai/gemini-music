# ADR 0003: Evidence-Gated Release Policy

- Status: Accepted
- Date: 2026-02-28
- Decision owners: Product + Engineering leadership

## Context

A release should prove readiness against product goals and leadership judging criteria, not only unit tests.

## Decision

Require evidence-gated releases using a combined chain of tests, behavioral evals, goal scenario validation, drift checks, and scorecard threshold gates.

Release signal source files:

- `api/evals/reports/latest_report.json`
- `api/evals/reports/project_goal_status.json`
- `api/evals/reports/eval_drift_snapshot.json`
- `api/evals/reports/release_gate_status.json`

## Consequences

Positive:

- Stronger confidence in shipping quality
- Explicit closure of ecosystem/business/rigor gaps
- Better traceability for executive-ready demos

Tradeoffs:

- Longer pre-release execution time
- More scripts/artifacts to maintain

## Enforcement

- Local gate: `make ci`
- Release block: `scripts/release.sh` exits on any failed gate
- Tag gate in CI: release workflow runs validation on `v*.*.*` tags
