# Git Cheat Sheet

## Purpose

One-page Git review sheet for AI Backend Engineer preparation.

Focused on the Git object model, the three-tree model, references, reset, and reflog.

---

## Core Mental Model

```text
Git is project history management, not just backup.
```

Git records who changed what, when, why, and how to recover it.

---

## Snapshot vs Diff

- Git's core model is a snapshot, not a pure diff.
- A commit stores a full snapshot but reuses references to unchanged objects.
- Only changed content becomes a new object; unchanged files are shared.
- Pure diff would make checking out old versions slow.

---

## Objects and History

| Concept | Meaning |
|---------|---------|
| Commit | Immutable snapshot of the project at a point in time |
| Repository | Object database: all commits, blobs, trees, branches, tags, full history |
| Working Directory | The editable files you currently see |
| Staging Area / Index | The blueprint of the next commit |
| Branch | A movable reference to a commit |
| HEAD | The current reference (usually to a branch) |
| Detached HEAD | HEAD points directly to a commit, not a branch |

Commits are immutable: content changes create new objects; identity comes from the content
hash.

---

## Three Trees Model

```text
              Repository
            (history snapshots)
                 ^
                 |
            git commit
                 |
        Staging Area / Index
        (next commit blueprint)
                 ^
                 |
              git add
                 |
       Working Directory
       (currently edited code)
```

Commands as tree movement:

- `git add` = Working Directory -> Index
- `git commit` = Index -> Repository
- `git checkout` = Repository -> Working Directory (depending on HEAD / branch)
- `git restore` = restore Working Directory or Index depending on arguments
- `git reset` = move branch / HEAD and optionally reset Index and Working Directory

---

## HEAD, Branch, Detached HEAD

```text
Normal:   HEAD -> branch -> commit
Detached: HEAD -> commit
```

- A branch is a movable reference; new commits move it forward.
- HEAD usually points to the current branch.
- In detached HEAD, a new commit is owned by no branch and can become unreachable.

---

## git reset

| Command | HEAD / Branch | Index | Working Directory |
|---------|---------------|-------|-------------------|
| `git reset --soft` | moves | unchanged | unchanged |
| `git reset --mixed` (default) | moves | reset | unchanged |
| `git reset --hard` | moves | reset | reset |

Use cases:

- `--soft`: undo the commit but keep changes staged.
- `--mixed`: unstage changes while keeping the code (the default "un-add").
- `--hard`: discard the pointer move plus staged and working changes.

---

## git reflog

- `git log` shows reachable history from the current branch.
- `git reflog` shows where HEAD has been.
- After a mistaken reset, find the old SHA in `git reflog`, then `git checkout <sha>` or
  `git reset --hard <sha>`.
- Dangling / unreachable commits are not garbage-collected immediately.

---

## Production Warnings

- Do not run `git add .` blindly; stage only what you intend to commit.
- Do not run `git reset --hard` before checking `git status`.
- `git reset --hard` can destroy uncommitted work; reflog does not recover un-committed edits.
- Protect work before dangerous commands: commit or stash first.

---

## Interview Phrases

- "Git tracks project history as immutable snapshots, not pure diffs."
- "A commit is an immutable snapshot; you create new commits instead of editing old ones."
- "A branch is a movable reference to a commit; branching does not copy the project."
- "HEAD is the current reference; in detached HEAD it points directly to a commit."
- "The Staging Area is the blueprint of the next commit."
- "The three-tree model explains every command as movement between Working Directory, Index, and Repository."
- "`reset --soft` moves the reference, `--mixed` also resets the Index, `--hard` also resets the Working Directory."
- "`git reflog` is my recovery net for mistaken HEAD movements."
