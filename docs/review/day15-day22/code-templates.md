# Day15–Day22 Engineering Templates

> Part of the **Day15–Day22 Engineering Foundations Second Brain**.
> Companion documents: [super-cheatsheet.md](super-cheatsheet.md) · [memory-map.md](memory-map.md) · [interview-qa.md](interview-qa.md) · [one-page.md](one-page.md)

This is the **execution** layer of the Second Brain: reusable commands and configuration patterns that actually appear in Day15–Day22. For the *why*, see [super-cheatsheet.md](super-cheatsheet.md); this file is for *doing*.

Rules honored here: every template is traceable to a repository source; each shell block states whether it is read-only, changes local state, or affects the remote; GitHub Actions versions match the repository examples; no real secrets appear; and YAML/GitHub Actions blocks were reviewed statically only (not executed).

---

## Template 1: Safely Inspect Git State

### Source
`docs/git/day15-git-fundamentals.md` (Production habits, three trees)

### Solves
Knowing what you are about to commit or reset before running any destructive command.

### Use When
Before `git commit`, `git reset`, `git merge`, or any operation that moves references.

### Do Not Use When
Never a wrong time — this is the safe default first step.

### Template
```bash
git status --short      # what is staged vs modified vs untracked
git diff                # unstaged changes (Working Tree vs Index)
git diff --staged       # staged changes (Index vs last commit)
git log --oneline -5    # recent history
```

### Inputs to Replace
None.

### State Changed
Read-only. Nothing in the Working Tree, Index, or Repository is modified.

### Failure Signals
None expected; if `git status` errors, you are not inside a Git repository.

### Security Notes
Safe. Avoid pasting output containing internal paths into public issues.

---

## Template 2: Create and Switch a Feature Branch

### Source
`docs/git/day16-branch-and-merge.md` (Concept 2, Exercise 2)

### Solves
Isolating independent work so `main` stays releasable.

### Use When
Starting any new feature, fix, or experiment.

### Do Not Use When
You intend to commit directly to `main` (avoid — that is the anti-pattern from Day17).

### Template
```bash
git switch -c feature/agent    # create + switch (a movable reference, not a copy)
# ...edit files...
git add -p                     # stage intentionally, not `git add .` blindly
git commit -m "Add /agent endpoint"
```

### Inputs to Replace
`feature/agent` (branch name), the commit message.

### State Changed
Local only. Creates a new branch reference and, after commit, moves that branch forward. The remote is untouched until you push.

### Failure Signals
`fatal: a branch named 'feature/agent' already exists` — pick another name or switch to it.

### Security Notes
Review staged content (`git diff --staged`) so secrets or large files are not swept in.

---

## Template 3: Sync a Feature Branch with the Remote

### Source
`docs/git/day17-github-workflow.md` (Exercise 1)

### Solves
Publishing local work so a Pull Request can be opened.

### Use When
Your branch is ready for collaboration, CI, and review.

### Do Not Use When
Pushing directly to `main` on a protected repository (it should be blocked by design).

### Template
```bash
git push -u origin feature/agent   # publish branch, set upstream tracking
# then open a Pull Request from feature/agent into main on GitHub
```

### Inputs to Replace
`feature/agent`.

### State Changed
Affects the remote: creates/updates the remote branch. Local branch gains an upstream. Does **not** modify `main`.

### Failure Signals
`updates were rejected` — the remote moved; fetch/rebase or merge before pushing again.

### Security Notes
Never push files containing credentials; the remote history is hard to scrub.

---

## Template 4: Locate a Change in History

### Source
`docs/git/day15-git-fundamentals.md` (Production Topics; FastAPI regression example)

### Solves
Finding the commit that introduced a regression, and what it changed.

### Use When
A route/prompt/config worked before and fails now.

### Do Not Use When
You already know the commit — go straight to `git show <sha>`.

### Template
```bash
git log --oneline --graph --decorate      # read the DAG (branches + merges)
git log -- path/to/file.py                 # history of one file (read-only)
git diff <good-sha> <bad-sha> -- path/to/file.py   # exact change between two commits
git show <sha>                             # full patch of one commit
```

### Inputs to Replace
`<good-sha>`, `<bad-sha>`, `<sha>`, file path.

### State Changed
Read-only. Inspects history without moving any reference.

### Failure Signals
`unknown revision` — the SHA/path is wrong; copy it from `git log`.

### Security Notes
Safe.

---

## Template 5: Pre-Merge Check and Merge-Strategy Selection

### Source
`docs/git/day18-merge-strategy-and-code-review.md` (Exercise 1); `docs/git/day16-branch-and-merge.md`

### Solves
Choosing the history shape `main` should keep when integrating a branch.

### Use When
Integrating a finished feature branch.

### Do Not Use When
Rebasing shared/published history (rebase rewrites identity — branch integration only).

### Template
```bash
git switch main
git log --oneline main..feature/agent      # preview what would merge (read-only)

git merge --no-ff feature/agent            # keep all commits + a merge commit
# OR: squash noisy history into one product commit
git merge --squash feature/agent && git commit -m "Add /agent endpoint"
# OR (branch integration only): linear history, commits kept, identity rewritten
git rebase main            # run on the feature branch, not on shared history
```

### Inputs to Replace
`feature/agent`, commit message.

### State Changed
Local: `--no-ff`/`--squash` move `main`; `git rebase` rewrites the feature branch's commit identities. None affect the remote until pushed.

### Failure Signals
`CONFLICT (content)` — Git refuses to guess intent; resolve, `git add`, then commit.

### Security Notes
Never force-push a rebased branch that others already pulled.

---

## Template 6: Recover a Mistaken Reset with reflog

### Source
`docs/git/day15-git-fundamentals.md` (Concept 10, Exercise 5)

### Solves
Restoring a commit after `git reset --hard HEAD~1` removed the branch reference.

### Use When
You lost *committed* work by moving a reference incorrectly.

### Do Not Use When
The work was never committed — reflog tracks commits/HEAD movement, not uncommitted edits.

### Template
```bash
git reflog                 # find where HEAD used to point (read-only)
git reset --hard <old-sha> # move the branch back to the recovered commit
# OR inspect first without moving the branch:
git switch --detach <old-sha>
```

### Inputs to Replace
`<old-sha>` from the reflog output.

### State Changed
`git reflog`/`git switch --detach` are inspection; `git reset --hard <old-sha>` moves the branch and resets the Working Tree (**destructive to current uncommitted edits**).

### Failure Signals
The SHA is absent from reflog — the object may have been garbage-collected after a long time.

### Security Notes
`--hard` discards current uncommitted work; stash or commit first if unsure.

---

## Template 7: Basic FastAPI CI Workflow

### Source
`examples/github-actions/fastapi-ci.example.yml`; `docs/devops/day21-github-actions-fundamentals.md` (Exercise 5)

### Solves
A repository-defined quality gate that runs on every push and PR.

### Use When
Adding CI to a real FastAPI project.

### Do Not Use When
This handbook repo — the example is intentionally not under `.github/workflows/` (no app to run).

### Template
```yaml
name: FastAPI CI
on:                          # `on` = when (trigger), NOT the OS
  push:
    branches: [main]
  pull_request:
jobs:
  quality:
    runs-on: ubuntu-latest   # `runs-on` = where (runner)
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4          # fresh runner has no code
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run Ruff
        run: ruff check .
      - name: Run tests
        run: pytest                        # quality gate
```

### Inputs to Replace
Python version, dependency file, commands.

### State Changed
Defines CI in the repo. On a real project each run creates fresh ephemeral runners; no local state.

### Failure Signals
A failing Ruff or pytest step fails the job and blocks a `needs: quality` build.

### Security Notes
Inject secrets only where needed via `${{ secrets.NAME }}`; never hardcode or print them.

---

## Template 8: Matrix Test Job with fail-fast

### Source
`examples/github-actions/github-actions-advanced.example.yml`; `docs/devops/day22-github-actions-advanced.md` (Concepts 1–2)

### Solves
Testing across supported Python versions from one job definition.

### Use When
Each version is an independent support commitment (use `fail-fast: false`).

### Do Not Use When
One early signal is enough (an expensive one-off probe) — prefer `fail-fast: true` there.

### Template
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false                 # each version's result is independent
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pytest
```

### Inputs to Replace
The version list; add axes (e.g. `os:`) only if needed (combinations multiply).

### State Changed
Generates one isolated job per combination. Jobs do **not** share a filesystem or installed dependencies.

### Failure Signals
With `fail-fast: false`, one version failing does not cancel the others; check each job.

### Security Notes
Cap matrix size to control runner-minutes; large matrices multiply cost.

---

## Template 9: Cache pip Downloads

### Source
`examples/github-actions/github-actions-advanced.example.yml`; `docs/devops/day22-github-actions-advanced.md` (Concept 3)

### Solves
Speeding up repeated dependency installs.

### Use When
Dependencies change rarely and are re-downloadable.

### Do Not Use When
Storing a run's official result — that is an artifact, not a cache.

### Template
```yaml
- name: Cache pip downloads
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Inputs to Replace
`path` and the `hashFiles(...)` dependency file for your package manager.

### State Changed
Adds a restorable cache keyed by OS + dependency hash. The workflow must still be correct on a cache miss (only slower).

### Failure Signals
A stale cache can hide a broken clean build — periodically verify with a cache miss.

### Security Notes
Do not cache secrets or credential files; caches can be restored by later runs.

---

## Template 10: Upload and Download a Test-Report Artifact

### Source
`examples/github-actions/github-actions-advanced.example.yml`; `docs/devops/day22-github-actions-advanced.md` (Concept 3)

### Solves
Moving a run's formal output between jobs that do not share a filesystem.

### Use When
A later job (report/deploy) needs this run's official result.

### Do Not Use When
The file is re-creatable acceleration data — cache it instead.

### Template
```yaml
- name: Upload test reports
  if: always()                       # upload even if tests failed
  uses: actions/upload-artifact@v4
  with:
    name: test-reports
    path: |
      coverage.xml
      junit.xml
    if-no-files-found: warn          # always() does not guarantee files exist
# In a dependent job:
#   report:
#     needs: test
#     steps:
#       - uses: actions/download-artifact@v4
#         with:
#           name: test-reports
```

### Inputs to Replace
Artifact `name`, `path` list.

### State Changed
Persists the named artifact for the run and makes it downloadable by dependent jobs.

### Failure Signals
Missing files warn (not fail) because of `if-no-files-found: warn`; a missing report is not success.

### Security Notes
Do not upload artifacts containing secrets or sensitive data; artifacts are retained and downloadable.

---

## Template 11: Reuse — Composite Action vs Reusable Workflow

### Source
`examples/github-actions/composite-python-quality/action.yml`; `examples/github-actions/reusable-fastapi-ci.example.yml`; `docs/devops/day22-github-actions-advanced.md` (Concept 4)

### Solves
Removing duplication at the right granularity: reusable **steps** vs reusable **jobs**.

### Use When
Composite Action for a repeated step sequence; Reusable Workflow for an org-wide pipeline.

### Do Not Use When
Placing a reusable workflow in a subdirectory — it must live directly under `.github/workflows/`.

### Template
```yaml
# Composite Action (reusable STEPS) — action.yml; runs inside the caller job
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
    - name: Run Ruff
      shell: bash               # every composite `run` must declare shell
      run: ruff check .
---
# Reusable Workflow (reusable JOBS) — .github/workflows/reusable-fastapi-ci.yml
on:
  workflow_call:
    inputs:
      python-version: { type: string, required: false, default: "3.12" }
permissions:
  contents: read
# ...defines full jobs with runs-on...
```

### Inputs to Replace
Inputs (`python-version`, requirements path, test command).

### State Changed
Defines reusable configuration; no runtime state until called. Composite via step-level `uses`; reusable workflow via job-level `uses: owner/repo/.github/workflows/file.yml@<sha>`.

### Failure Signals
Calling a reusable workflow from an `examples/` path fails — copy it under `.github/workflows/` first.

### Security Notes
Neither may hardcode secrets. Prefer pinning a called reusable workflow to a commit SHA over `@main` (a branch ref can move).

---

## Template 12: Reliable Deployment — Build Once, Deploy the Immutable Digest

### Source
`examples/github-actions/github-actions-advanced.example.yml`; `docs/devops/day22-github-actions-advanced.md` (Concept 6)

### Solves
Deploying exactly what was tested — protected, serialized, and recoverable.

### Use When
Promoting a verified release candidate to production.

### Do Not Use When
Rebuilding in the deploy job, or deploying a mutable `:latest` tag (breaks "tested = deployed").

### Template
```yaml
deploy:
  needs: [build, verify-image]     # deploy only after the exact image is verified
  if: startsWith(github.ref, 'refs/tags/v')   # tag-only
  runs-on: ubuntu-latest
  environment: production          # required reviewers + production Secrets
  concurrency:
    group: production              # all prod deploys share one lock
    cancel-in-progress: false      # queue; never interrupt an active deploy
  steps:
    - name: Deploy immutable digest
      env:
        IMAGE: ghcr.io/${{ github.repository }}@${{ needs.build.outputs.image-digest }}
        DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}   # production-only secret
      run: echo "Deploying $IMAGE"   # ./deploy.sh "$IMAGE"
```

### Inputs to Replace
Registry/image reference, deploy command, secret name.

### State Changed
Mutates the production environment (external). Serialized by the concurrency group; gated by required reviewers.

### Failure Signals
Cancelling an in-progress prod deploy risks half-applied migrations and mixed-version fleets — keep `cancel-in-progress: false`.

### Security Notes
Production Secrets live only in the deploy job/environment, never in general CI jobs; deploy the digest (`@sha256:...`), never `:latest`.

---

# Source Map

| Template | Repository Source |
|---|---|
| 1. Inspect Git state | `docs/git/day15-git-fundamentals.md` |
| 2. Create/switch branch | `docs/git/day16-branch-and-merge.md` |
| 3. Sync remote | `docs/git/day17-github-workflow.md` |
| 4. Locate a change | `docs/git/day15-git-fundamentals.md` |
| 5. Merge-strategy selection | `docs/git/day18-merge-strategy-and-code-review.md`, `docs/git/day16-branch-and-merge.md` |
| 6. reflog recovery | `docs/git/day15-git-fundamentals.md` |
| 7. Basic FastAPI CI | `examples/github-actions/fastapi-ci.example.yml`, `docs/devops/day21-github-actions-fundamentals.md` |
| 8. Matrix + fail-fast | `examples/github-actions/github-actions-advanced.example.yml`, `docs/devops/day22-github-actions-advanced.md` |
| 9. Cache pip | `examples/github-actions/github-actions-advanced.example.yml`, `docs/devops/day22-github-actions-advanced.md` |
| 10. Artifact upload/download | `examples/github-actions/github-actions-advanced.example.yml`, `docs/devops/day22-github-actions-advanced.md` |
| 11. Composite vs Reusable | `examples/github-actions/composite-python-quality/action.yml`, `examples/github-actions/reusable-fastapi-ci.example.yml`, `docs/devops/day22-github-actions-advanced.md` |
| 12. Reliable deployment | `examples/github-actions/github-actions-advanced.example.yml`, `docs/devops/day22-github-actions-advanced.md` |
