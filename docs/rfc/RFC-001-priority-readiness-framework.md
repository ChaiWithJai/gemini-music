# RFC-001: Priority Readiness Framework (Retroactive)

- Status: Accepted
- Date: 2026-02-28
- Related: `LEADERSHIP_PRIORITY_SCORECARD.md`, `docs/prd/PRD-001-platform.md`

## Summary

Define a repeatable engineering governance model that maps implementation and release decisions to leadership judging criteria and product goals.

## Motivation

We need repeatable proof, not one-off demos. The framework must turn product goals into enforceable engineering gates.

## Judging Criteria Mapping

- A: Frontier product novelty
- B: User value proof
- C: Scale readiness
- D: Ecosystem leverage
- E: Safety, privacy, rights
- F: Measurable business signal
- G: Scientific/eval rigor

Priority-ready threshold:

- Total >= 85
- Demis lens >= 40
- Sundar lens >= 40

## Proposal

Adopt evidence-gated delivery where every release candidate includes:

- Automated eval report (`latest_report.json`)
- Goal scenario report (`project_goal_status.json`)
- Drift snapshot report (`eval_drift_snapshot.json`)
- Release gate report (`release_gate_status.json`)

## Sub-RFCs

- `RFC-001D-ecosystem-leverage.md`
- `RFC-001F-business-signal.md`
- `RFC-001G-eval-rigor.md`

## Risks

- Gate inflation without real signal
- Overfitting to scorecard artifacts

## Mitigations

- Keep behavioral test cases tied to real API contracts
- Track delta vs baseline and confidence bounds
- Require both technical and product signal before release
