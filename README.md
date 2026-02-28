# Gemini Music

Real-time personalized mantra learning + AI-assisted kirtan using adaptive signals from listener input, optional biometrics, and environment context.

## Day 0 Story (Clone -> Run -> Contribute -> Merge -> Release)

1. Clone and enter the repo.
```bash
git clone git@github.com:ChaiWithJai/gemini-music.git
cd gemini-music
```

2. Bootstrap a known-good local environment.
```bash
./scripts/day0.sh
```

3. Start the API and open local docs.
```bash
cd api
make run
# open http://localhost:8000/docs
# open http://localhost:8000/poc/
# open http://localhost:8000/demo/
```

4. Make a contribution on a feature branch.
```bash
git checkout -b codex/<short-feature-name>
# edit code/docs
cd api
make ci
```

5. Push and open a PR.
```bash
git add -A
git commit -m "feat: <what changed>"
git push -u origin HEAD
gh pr create --fill
```

6. Merge after checks pass.
```bash
gh pr merge --squash --delete-branch
```

7. Cut a release from `main`.
```bash
cd ..
./scripts/release.sh v0.2.0
```

8. Rehearse executive demo + build submission dossier.
```bash
./scripts/rehearse_demo.sh
./scripts/build_submission_dossier.sh
```

## Developer Commands

From `api/`:

- `make doctor`: verify Python 3.13 toolchain and venv compatibility
- `make bootstrap`: create/recreate `.venv` for Python 3.13
- `make install`: install dependencies
- `make test`: run unit and API tests
- `make evals_all`: run full scorecard eval set
- `make goal_test`: run focused goal scenario and produce single JSON status report
- `make bench_adaptive`: 30-run adaptive-vs-static benchmark with CI95
- `make load_benchmark`: concurrent load/latency benchmark (p50/p95/p99 + error rate)
- `make chaos_reliability`: reliability scenarios (no biometrics, noisy audio, transient fallback)
- `make seed_repro`: deterministic seeded reproducibility check
- `make ai_kirtan_quality`: payload contract + quality rubric artifact
- `make adapter_verify`: wearable/content adapter starter-kit verification
- `make ci`: full local quality gate chain
- `make release_gate`: enforce score and drift thresholds

## Product, Decision, and Delivery Docs

- Product scope: `PROJECT_SCOPE.md`
- Leadership scorecard: `LEADERSHIP_PRIORITY_SCORECARD.md`
- API overview: `api/README.md`
- Documentation index: `docs/README.md`
- ADRs: `docs/adr/`
- PRDs: `docs/prd/`
- RFCs: `docs/rfc/`
- Runbooks: `docs/runbooks/`

## DevOps Philosophy

- Pin runtime to Python 3.13 for deterministic local and CI behavior.
- Fail fast on environment drift (`make doctor`).
- Keep release confidence evidence-first: tests, evals, benchmarks, chaos checks, drift snapshot, release gate.
- Treat artifacts in `api/evals/reports/` as release evidence.

## Release Policy

- Release tags use semver: `vMAJOR.MINOR.PATCH`.
- `scripts/release.sh` blocks release if git is dirty or local CI fails.
- GitHub Actions runs CI for PRs/pushes and release validation for tags.
