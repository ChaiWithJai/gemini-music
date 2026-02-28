# RFC-001F: Business Signal Instrumentation and Decisioning

- Parent: `RFC-001-priority-readiness-framework.md`
- Status: Accepted
- Date: 2026-02-28
- Target dimension: F (Measurable business signal)

## Problem

We need durable evidence that adaptive behavior produces business-relevant outcomes.

## Proposal

Adopt daily business signal projections and experiment comparison endpoints as first-class release evidence.

Core surfaces:

- `business_signal_daily` projection table
- `/v1/analytics/business-cohorts`
- `/v1/analytics/experiments/adaptive-vs-static`
- `scripts/generate_weekly_kpi_report.py`

## Metrics

- Sessions started/completed
- Meaningful sessions
- Adaptation helpful rate
- Day-7 returning users
- Bhav pass rate

## Success Criteria

- Dimension F weighted score meets release threshold.
- Weekly KPI report is generated in CI/release path.
- Experiment endpoint returns confidence interval bounds.

## Risks and Controls

- Risk: vanity metrics with weak causal signal.
- Control: preserve adaptive-vs-static comparisons and CI intervals in artifacts.
