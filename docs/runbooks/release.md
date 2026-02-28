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
- `make drift_snapshot`
- `make release_gate`

Use one command:

```bash
make ci
```

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
