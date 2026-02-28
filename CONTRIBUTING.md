# Contributing

## Branching and Commits

- Base branch: `main`
- Feature branch prefix: `codex/`
- Commit format: conventional style (`feat:`, `fix:`, `chore:`, `docs:`)

Example:
```bash
git checkout -b codex/improve-release-gates
```

## Local Quality Gates

Before opening a PR:

```bash
cd api
make ci
```

Minimum expectation for contribution readiness:

- Tests pass (`make test`)
- Scorecard evals pass (`make evals_all`)
- Goal scenario passes (`make goal_test`)
- Release gate passes (`make release_gate`)

## Pull Request Checklist

- Scope is small, focused, and reversible.
- Tests were added or updated for behavior changes.
- Docs were updated if commands, APIs, or behavior changed.
- Risk and rollback notes are included in the PR body.

## Merge Policy

- Prefer squash merge for feature branches.
- Merge only when GitHub checks are green.
- Delete merged branches.

## Release Workflow

- Use `scripts/release.sh` from a clean `main` branch.
- Do not cut a tag if local quality gates fail.
- Prefer one release per coherent change set.

## Security and Privacy

- Do not commit secrets.
- Do not store raw biometric/audio data unless explicitly required and documented.
- Keep privacy defaults conservative.
