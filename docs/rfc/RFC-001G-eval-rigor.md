# RFC-001G: Eval Rigor and Drift Governance

- Parent: `RFC-001-priority-readiness-framework.md`
- Status: Accepted
- Date: 2026-02-28
- Target dimension: G (Scientific/eval rigor)

## Problem

Claims of readiness are weak without repeatability, confidence bounds, and drift controls.

## Proposal

Formalize eval rigor with:

- Multi-attempt behavioral eval execution
- Pass-rate confidence intervals
- Baseline drift snapshots and release blocking

Implemented controls:

- `evals/run_evals.py` confidence interval reporting
- `scripts/capture_eval_drift_snapshot.py`
- `scripts/check_release_gates.py` drift guard + score thresholds

## Success Criteria

- Dimension G score passes release threshold.
- Drift status is PASS for release.
- No ALWAYS_PASSES case failures.

## Risks

- Test flakiness creates false negatives.
- Overly strict thresholds may block healthy iteration.

## Mitigations

- Use policy tiers (`ALWAYS_PASSES`, `USUALLY_PASSES`) with bounded retries.
- Revisit thresholds only through ADR/RFC updates.
