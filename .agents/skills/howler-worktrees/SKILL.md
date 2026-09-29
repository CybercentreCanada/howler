---
name: howler-worktrees
description: Run the isolated worktree, adversarial review, and patch-application workflow for large Howler implementation tasks; do not use for minor localized fixes.
---

# Howler Worktree Orchestration

Use this skill only for large implementation tasks: substantial multi-file features/refactors, cross-package changes, migrations, broad test-suite work, or work with significant coordination risk. Do not use it for minor localized changes such as a low-risk single-file bugfix or small documentation edit; implement those directly in the primary working tree with focused validation. First read the root `AGENTS.md` and inspect the repository state. Do not provision branches/worktrees just because a task could theoretically be parallelized; get explicit authorization before changing Git state.

## Safety contract

- Run helpers from a shell at the Howler repository or one of its worktrees. Source [`scripts/worktree-helpers.sh`](./scripts/worktree-helpers.sh).
- Helpers use `.worktrees/`, which must stay ignored. The primary checkout remains on its current branch and is the final destination. Agents use `.worktrees/<task>-<role>` on `agent/<task>/<role>`; there is no integration feature branch/worktree.
- `orchestrate_start` pins the task to the primary checkout's current `HEAD` without changing the checkout. Never silently switch branches, pull, or assume `main`/`develop` is the target.
- Before dispatch, define narrow allowed/forbidden glob patterns, interfaces, and package-specific verification. Allowed file sets must be pairwise disjoint across all agents. `orchestrate_spawn` writes the pinned base and these boundaries into the worktree's root `TASK.md`; `orchestrate_patch` rejects changed paths outside the declared allowed set or matching the forbidden set. Never include this coordination manifest in the patch.
- Run implementation and focused validation in the assigned worktree. A separate reviewer must adversarially inspect the full diff against the base and task contract, including negative cases, repository invariants, security, changed-path ownership, and test evidence. Require an explicit `APPROVED` verdict with no unresolved blocking/high findings; otherwise return findings to the owning agent and review a fresh diff.
- Only after approval, create a local checkpoint commit on the agent branch containing only its approved, owned files. `orchestrate_patch` generates `.agent.patch` inside that worktree, retains a copy under `.worktrees/`, and requires the `--review-approved` acknowledgement. Inspect the patch's paths. In the primary checkout, `orchestrate_apply` checks that the base is unchanged, rejects paths already modified there, runs `git apply --check`, then applies the patch without merging branches. Apply patches sequentially and stop on any failure or overlap.
- After applying all approved patches, inspect the primary working tree diff and run relevant Howler package checks there. If validation reveals an integration-only defect, assign it to a new worktree from the current primary `HEAD`; obtain another adversarial approval and apply its patch in the same way.
- `orchestrate_teardown` only removes a clean named worktree after its retained patch reverse-checks against the primary checkout. It removes only the generated untracked `TASK.md` and `.agent.patch`; the agent branch and retained patch copy are kept for recovery. Helpers never force-remove, prune, push, or create PRs.
- If a helper refuses an operation, inspect the status and resolve the specific cause; do not bypass its checks or remove user data.

## Usage

```bash
source .agents/skills/howler-worktrees/scripts/worktree-helpers.sh

# Pin to the current primary checkout HEAD; no branch is created or switched.
orchestrate_start <task-name> HEAD

# Create an isolated branch/worktree and an ownership/verification manifest.
orchestrate_spawn <task-name> <role> '<allowed/glob,patterns>' '<forbidden/glob,patterns>' '<contract>' '<verification command>'

# After independent adversarial review approves, commit only owned code files in the agent branch.
# Then generate and inspect the patch.
orchestrate_patch <task-name> <role> --review-approved

# From the primary repository root, check and apply that approved patch.
orchestrate_apply <task-name> <role> --review-approved

# After root validation, optionally remove the clean source worktree; branch and patch are kept.
orchestrate_teardown <task-name> <role> --patch-applied
```

Run `orchestrate_start` and `orchestrate_spawn` only after the user authorizes creating the named branches/worktrees. Before `orchestrate_apply`, verify the reviewer verdict, inspect `git status` and the patch, and run the exact `git apply --check` gate. Run teardown only after authorization, root validation, and inspecting `git worktree list`. Keep the primary checkout's branch/history unchanged; leave agent branches and patch files for recovery.
