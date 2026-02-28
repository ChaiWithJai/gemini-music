# Runbook: Day 0 Developer Journey

## Goal

A new developer should be able to clone, run locally, contribute, merge, and prepare a release candidate on Day 0.

## Preconditions

- macOS or Linux
- Git
- GitHub CLI (`gh`) authenticated
- Python 3.13 available

## Step 1: Clone

```bash
git clone git@github.com:ChaiWithJai/gemini-music.git
cd gemini-music
```

## Step 2: Bootstrap

```bash
./scripts/day0.sh
```

What this does:

- Verifies Python 3.13 availability
- Bootstraps `api/.venv`
- Installs dependencies
- Runs tests
- Runs the full quality chain with `make ci`

## Step 3: Run Locally

```bash
cd api
make run
```

Validate:

- API docs: `http://localhost:8000/docs`
- POC UI: `http://localhost:8000/poc/`

## Step 4: Make a Contribution

```bash
git checkout -b codex/<feature-name>
# make changes
cd api
make ci
```

## Step 5: Open PR

```bash
git add -A
git commit -m "feat: <change summary>"
git push -u origin HEAD
gh pr create --fill
```

## Step 6: Merge

```bash
gh pr merge --squash --delete-branch
```

## Step 7: Release Candidate

From clean `main`:

```bash
./scripts/release.sh v0.2.0 --dry-run
```

Then cut real release:

```bash
./scripts/release.sh v0.2.0
```

## Day 0 Done Criteria

- Local API and POC run successfully
- Local CI chain passes
- PR merged with green checks
- Release tag pushed or dry-run validated
