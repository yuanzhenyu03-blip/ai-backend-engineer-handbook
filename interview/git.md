# Git Interview

## Purpose

Interview questions and model answers for Git workflows and collaboration.

## Sections

- Commits
- Branches
- Merge vs Rebase
- Pull Requests
- Conflict Resolution
- Release Workflow
- Team Collaboration

---

# Day15 Git Fundamentals Questions

These questions come from the Day15 Git Fundamentals lesson. They focus on the Git object
model, the three-tree model, references, reset, and reflog.

## Beginner

### 1. What is Git?

Question:

What is Git?

中文解析:

Git 是分布式版本控制系统。它把项目历史记录为不可变快照，让工程师协作、审查改动、排查回归并安全回滚。

Standard Answer:

Git is a distributed version control system. It tracks project history as immutable snapshots,
allowing engineers to collaborate, review changes, debug regressions, and roll back safely.

Follow-up Question:

Why is Git more than a backup tool?

### 2. What is a commit?

Question:

What is a commit?

中文解析:

commit 是项目在某个时间点的不可变快照。它记录项目状态并指向父提交。

Standard Answer:

A commit is an immutable snapshot of the project at a specific point in time. It records the
project state and points to its parent commit.

Follow-up Question:

Why can an old commit not be modified in place?

### 3. What is a repository?

Question:

What is a repository?

中文解析:

仓库是对象数据库，包含所有 commit、blob、tree、分支、标签和完整历史，而不仅仅是当前项目。

Standard Answer:

A repository is an object database containing all commits, blobs, trees, branches, tags, and
full history — not just the current project files.

Follow-up Question:

How is the repository different from the Working Directory?

### 4. What is a branch?

Question:

What is a branch?

中文解析:

分支是指向某个 commit 的可移动引用。新建分支不复制项目，只是创建一个新引用。

Standard Answer:

A branch is a movable reference to a commit. Creating a branch does not copy the project; it
creates a new reference.

Follow-up Question:

What moves a branch reference forward?

### 5. What is HEAD?

Question:

What is HEAD?

中文解析:

HEAD 表示当前所在位置。通常指向当前分支，分支再指向 commit；在 detached HEAD 状态下直接指向一个 commit。

Standard Answer:

HEAD represents the current position in Git. Usually it points to the current branch, which
points to a commit. In detached HEAD state, HEAD points directly to a commit.

Follow-up Question:

What is the normal chain from HEAD to a commit?

## Intermediate

### 1. Snapshot vs diff.

Question:

Does Git store diffs or snapshots?

中文解析:

Git 核心模型是快照，不是纯 diff。commit 存快照，但对未改动的对象复用引用，只为改动内容创建新对象。

Standard Answer:

Git's core model is a snapshot, not a pure diff. A commit stores a snapshot but reuses
references to unchanged objects, creating new objects only for changed content.

Follow-up Question:

Why would pure diff make checking out old versions slow?

### 2. Working Directory vs Staging Area vs Repository.

Question:

Explain the three trees.

中文解析:

工作区是正在编辑的文件；暂存区（Index）是下一个 commit 的蓝图；仓库存储历史快照。git add 从工作区到 Index，git commit 从 Index 到仓库。

Standard Answer:

The Working Directory is the edited files, the Staging Area (Index) is the blueprint of the
next commit, and the Repository stores history. `git add` moves Working Directory to Index;
`git commit` moves Index to Repository.

Follow-up Question:

Which tree does `git commit` build the snapshot from?

### 3. Why commit from the Staging Area?

Question:

Why does `git commit` build from the Index instead of the Working Directory?

中文解析:

暂存区让开发者先选择和准备要提交的内容。commit 基于暂存的版本，所以能精确控制每次提交包含什么。

Standard Answer:

The Staging Area lets the developer select and prepare exactly what to commit. The commit is
built from the staged version, giving precise control over what each commit contains.

Follow-up Question:

If the Working Directory has v2 but the Index has v1, what does the commit save?

### 4. What is detached HEAD?

Question:

What is detached HEAD?

中文解析:

detached HEAD 指 HEAD 直接指向一个 commit 而不是分支。若在此创建新 commit，没有分支引用它，切走后它可能变成不可达对象。

Standard Answer:

Detached HEAD means HEAD points directly to a commit instead of a branch. A new commit made
there is referenced by no branch and can become unreachable after switching away.

Follow-up Question:

How would you keep a commit made in detached HEAD?

### 5. What happens after checkout to an old commit?

Question:

What happens when you check out an old commit?

中文解析:

工作区切换到那个快照，HEAD 进入 detached 状态，但更新的 commit 不会被删除，仍在仓库里。

Standard Answer:

The Working Directory switches to that snapshot and HEAD becomes detached, but newer commits
are not deleted — they still exist in the repository.

Follow-up Question:

Does checkout ever delete later commits?

## Senior

### 1. Why are commits immutable?

Question:

Why are commits immutable?

中文解析:

因为 commit 的身份来自内容哈希。修改旧 commit 会改变哈希并破坏后续历史。不可变让回滚可靠。

Standard Answer:

Because a commit's identity comes from its content hash. Modifying an old commit would change
its hash and corrupt later history. Immutability is what makes rollback reliable.

Interview Review:

Strong answers connect immutability to reliable history and rollback.

Production Case:

Rolling back a broken deploy is safe because old snapshots remain stable.

### 2. Why are branches movable references?

Question:

Why are branches just movable references?

中文解析:

分支只是指向 commit 的指针，所以新建和切换分支很廉价，不复制项目。提交时移动引用，而不修改旧快照。

Standard Answer:

A branch is only a pointer to a commit, so creating and switching branches is cheap and does
not copy the project. Committing moves the reference forward without mutating old snapshots.

Interview Review:

Good answers relate this to Python reference reassignment.

Production Case:

Feature branches let teams work in parallel without duplicating the codebase.

### 3. Explain reset soft/mixed/hard with the three trees.

Question:

Explain `reset --soft`, `--mixed`, and `--hard`.

中文解析:

--soft 只移动 HEAD/分支；--mixed（默认）还重置 Index；--hard 还重置工作区。--hard 会丢失未提交的改动。

Standard Answer:

`reset --soft` moves HEAD or the branch only. `reset --mixed` also resets the Index. `reset
--hard` resets HEAD, the Index, and the Working Directory. `--hard` can lose uncommitted work.

Interview Review:

Strong answers map each mode to the three trees.

Production Case:

Use `--soft` to reshape the last commit; avoid `--hard` before checking `git status`.

### 4. How would you recover from a mistaken hard reset?

Question:

How do you recover from a mistaken `git reset --hard`?

中文解析:

用 git reflog 找到旧 commit 的 SHA，再 git checkout 或 git reset --hard 到它。commit 仍作为不可达对象存在。但未提交的改动无法通过 reflog 恢复。

Standard Answer:

Use `git reflog` to find the old commit's SHA, then `git checkout <sha>` or `git reset --hard
<sha>`. The commit still exists as an unreachable object. However, changes that were never
committed cannot be recovered by reflog.

Interview Review:

Look for the distinction between committed and un-committed work.

Production Case:

Reflog recovers a branch tip that was reset away by mistake.

### 5. How does Git help production rollback?

Question:

How does Git support production rollback?

中文解析:

Git 保存不可变历史，可以用 git log/diff 定位引入问题的 commit，然后回滚到已知良好的快照。

Standard Answer:

Git keeps immutable history, so you can use `git log` and `git diff` to locate the commit that
introduced a problem and roll back to a known-good snapshot.

Interview Review:

Strong answers mention locating the regression, not just reverting blindly.

Production Case:

When `/chat` returns 500 after a deploy, find the suspect commit and roll back while you fix
it.

### 6. How does clean commit history improve code review?

Question:

Why does clean commit history matter in code review?

中文解析:

小而聚焦、说明"为什么"的提交让审查者能理解每个改动的意图，也让排查回归和回滚更容易。提交就是团队的文档。

Standard Answer:

Small, focused commits with messages that explain why make each change easy for reviewers to
understand, and make regressions and rollbacks easier to handle. Commits are team
documentation.

Interview Review:

Senior answers treat commit quality as an engineering asset.

Production Case:

Separating a prompt change from backend logic lets reviewers evaluate each independently.

### 7. How does Git's object model relate to Python's object model?

Question:

How does Git's object model relate to Python's object model?

中文解析:

Git 是 Python 对象模型在项目历史层面的工程实践。Commit/Tree/Blob 是不可变对象，Branch 和 HEAD 是引用；就像 Python 里对象不可变、名字是引用、身份用 id 区分。commit hash 相当于对象身份，移动分支相当于重新绑定名字。

Standard Answer:

Git applies the Python object model to project history. Commits, trees, and blobs are immutable
objects, and branches and HEAD are references, just like Python objects are values and names are
references. A commit hash is like object identity, and moving a branch is like rebinding a name.
Unchanged blobs and trees are shared between commits the same way Python shares references
instead of copying.

Interview Review:

Strong answers show that Git is not new knowledge but the object model applied to history.

Production Case:

Understanding this makes rollback, diffing, and branching intuitive across FastAPI, Playwright,
Docker, and prompt files.
