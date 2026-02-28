# Runbook: Release

## Release Inputs

- Clean `main` branch
- Passing local quality gates
- Changelog-ready commit set

## Mandatory Gates

From `api/` the release path must pass:

- `make test`
- `make evals_all`
- `make goal_test`
- `make poc_test`
- `make bench_adaptive`
- `make load_benchmark`
- `make chaos_reliability`
- `make seed_repro`
- `make ai_kirtan_quality`
- `make adapter_verify`
- `make drift_snapshot`
- `make release_gate`
- `make release_evidence_summary`

Use one command:

```bash
make ci
```

Hard-mode victory thresholds enforced by `make release_gate`:

- Scorecard total `>= 93`
- Demis lens `>= 45`
- Sundar lens `>= 45`
- Repeated confidence `>= 30` attempts with CI95 low `>= 0.8`

Manual evidence inputs are versioned in `api/evals/manual_evidence.json` and must be reviewed before release.

## Cut a Release

From repo root:

```bash
./scripts/release.sh v0.2.0
```

The script:

- Confirms clean git state
- Pulls latest `main`
- Runs local CI chain in `api/`
- Creates annotated git tag
- Pushes `main` and tag
- Creates GitHub release notes (if `gh` is installed)
- Uploads evidence bundle + criteria summary to the GitHub release

## Dry Run

```bash
./scripts/release.sh v0.2.0 --dry-run
```

## Rollback

If release is bad but not consumed:

1. Revert offending commit on `main`
2. Cut patch release `vX.Y.Z+1`
3. Document incident in follow-up RFC/ADR

If tag must be removed before public use:

```bash
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0
```

## Evidence Artifacts

Release evidence is generated under:

- `api/evals/reports/latest_report.json`
- `api/evals/reports/project_goal_status.json`
- `api/evals/reports/release_gate_status.json`
- `api/evals/reports/eval_drift_snapshot.json`
- `api/evals/reports/adaptive_vs_static_benchmark.json`
- `api/evals/reports/load_latency_benchmark.json`
- `api/evals/reports/chaos_reliability_report.json`
- `api/evals/reports/seed_reproducibility_report.json`
- `api/evals/reports/ai_kirtan_quality_report.json`
- `api/evals/reports/adapter_starter_kit_verification.json`
- `api/evals/reports/weekly_kpi_report.json`
- `api/evals/reports/release_evidence_summary.md`
