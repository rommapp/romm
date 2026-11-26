---
name: pr-ready
description: Run the pre-submit gauntlet (security-audit, code-review, simplify, review-polish, plain-prose, humanizer) over a change before opening or merging a PR.
argument-hint: "[PR number | branch | nothing for the current branch]"
disable-model-invocation: true
---

# PR-ready gauntlet

Run the review passes RomM applies to every non-trivial PR over one fixed
range. They run in parallel and land in this order. Do not skip a step or
reorder the commits.

## Target

`$ARGUMENTS` is a PR number, a branch, or nothing (the current branch). Resolve
it to a fetched target and derive `$BASE` and `$RANGE` before step 1, then
reuse `$RANGE` for every step but the last. `HEAD` is the right target only when
`$ARGUMENTS` is empty, so run the dispatch rather than assuming it: skip it and
every pass reviews the current checkout instead of what was asked for.

```bash
set -eu

git fetch origin master

case "$ARGUMENTS" in
"") TARGET="$(git rev-parse HEAD)" ;;
# a pull ref needs its own refspec, the fetch above will not create it
*[!0-9]*) git fetch origin "$ARGUMENTS"; TARGET="$(git rev-parse FETCH_HEAD)" ;;
*) git fetch origin "pull/$ARGUMENTS/head"; TARGET="$(git rev-parse FETCH_HEAD)" ;;
esac

BASE="$(git merge-base origin/master "$TARGET")"
RANGE="$BASE..$TARGET"
```

An all-digit argument is a PR number, anything else is a branch.

`set -e` is load-bearing here, because each failure otherwise fails open. A base
fetch that dies on the network, an argument that resolves to nothing, a missing
merge base: each leaves a side of `$RANGE` empty, and git reads an empty side as
`HEAD`, so `..$TARGET` is a valid range over the wrong commits rather than an
error. Abort on the first failure instead of handing every pass a range built
without the thing you asked them to review.

## Before steps 2 to 5

Step 1 is read-only and runs against `$RANGE` from wherever you are. The rest
are not: they rewrite files and run the repository's own code from the target
ref, including test runners, builds, `trunk`, package lifecycle scripts, and git
hooks. A clean step 1 verdict is no substitute for that, since an audit can miss
what it is looking for. So run steps 2 to 5 only on a ref you trust. On anything
else, stop after step 1 and report, or run the rest in an isolated environment
with no credentials and no network.

They also need the target checked out. Checking out a fetched sha detaches
`HEAD`, where each step's commits belong to no branch and go away on the next
switch, so give the work a branch first:

```bash
git switch -c "pr-ready/$(git rev-parse --short "$TARGET")" "$TARGET"
```

Those commits are local either way. They reach the PR only if you can push to
its source branch, so on a fork you cannot write to, the summary is the
deliverable and the commits are not.

Skip the branch when the target is already the current one. There, uncommitted
work counts as part of the change under review: commit it, since the agents'
worktrees see only commits, and stash anything unrelated, so each step's edits
stay attributable.

## Steps

1. **`security-audit`** over `$RANGE`. Read-only. Stop on a `malicious`
   verdict; `needs attention` is a finding for step 2, not a stop.
2. **`code-review` at `xhigh` with `--fix`**, targeting the resolved target
   rather than "the current diff", so it sees the whole change.
3. **`simplify`**, so it can simplify the correctness fixes too.
4. **`review-polish`**: §A to §D shape the code, and the §E verification gate
   has to cover everything the earlier steps rewrote.
5. **`plain-prose`, then `humanizer`**, over the prose `$RANGE` adds or changes,
   and again over what step 2 adds. See "Prose scope" below.

Each step that changes files ends in its own commit, named after the step. A bad
automated fix is then one `git revert` away instead of tangled with the other
passes.

## Running the steps in parallel

On a trusted ref, run the reviews at the same time over the same `$RANGE`,
then merge their commits in step order. On an untrusted ref, step 1 runs alone
first (see above), and the rest follow only on a clean verdict.

**Fan out.** The checkout must be at `$TARGET` with a clean tree, because each
agent's worktree starts from `HEAD`. In one message, start these background
agents with the Agent tool:

| Agent      | Isolation        | Does                                                        |
| ---------- | ---------------- | ----------------------------------------------------------- |
| `security` | none (read-only) | Step 1. Returns the verdict and findings.                   |
| `simplify` | `worktree`       | Step 3 over `$RANGE`.                                       |
| `polish`   | `worktree`       | Step 4 §A to §D only. Not §E.                               |
| `prose`    | `worktree`       | Step 5 over `$BASE`. Also returns the PR description edits. |

Then run step 2 in this session while they work. `code-review` and
`security-audit` fan out reviewers of their own, and a subagent cannot start
subagents, so step 2 stays here and the `security` agent runs the audit's
direct pass. If it returns `needs attention` on an area, deepen that area here
after step 2.

The agents never see step 2's fixes, so catch up on them while you wait. Right
after step 2's commit, `prose_check.py extract --diff $TARGET` lists exactly
the prose step 2 added: run step 5 over it. Run `simplify` over step 2's commit
too when it changed more than about 50 lines. Commit each as its step.

Each agent's prompt carries:

- `$BASE`, `$RANGE` and `$TARGET`, and the step to run. It invokes the skill
  with the Skill tool, or reads its `SKILL.md` for `humanizer` (see "Prose
  scope").
- Stay inside the files `$RANGE` touches. Commit once, named after the step
  (`pr-ready: simplify`). Never push.
- Run only the tests its edits affect, with a `ROMM_TEST_DB_TAG` of its own name.
  No browser pass, no Storybook, no §E gate.
- Return the commit sha, or "no changes", and a short list of what it changed.

A `malicious` verdict from the `security` agent stops the run when it arrives:
stop the other agents, reset the branch to `$TARGET`, and report.

**Merge in step order.** When every agent is back, cherry-pick the `simplify`,
`polish` and `prose` commits onto step 2's commits, in that order. On a
conflict, keep the earlier step's hunk, then reapply the later step's intent by
hand if it still applies. Never resolve with `-X theirs` or `-X ours` across a
whole commit.

**Verify once.** Run `review-polish` §E on the merged branch: the checks for
what the whole range touched, the browser pass for a UI change, and the
screenshots and `mermaid` block §F asks for.

Finish with one consolidated summary rather than per-agent transcripts: the
security verdict, what steps 2 to 5 changed by area, which checks ran and their
results, any conflict you resolved by hand, and anything still needing a human
decision. It also carries what the PR description needs: the `prose` agent's
edits, the screenshots §E captured, which `gh ... --attach` uploads under the
`Screenshots` heading, and the `mermaid` block for a change that moved a
boundary.

The agents keep their transcripts out of this session, so even a large diff
fits in one run.

## Prose scope

First apply `.claude/skills/plain-prose/SKILL.md` to the units
`python3 backend/tools/prose_check.py extract --diff $BASE` lists. It covers the
API descriptions and `en_US` strings that `humanizer` skips below.

Then read `.claude/skills/humanizer/SKILL.md` and apply it rather than invoking the
skill, since a personal install of the same name would load instead. In file
mode it edits the Markdown paragraphs the range touches, and comments and
docstrings on added lines. Skip locale files, paths in the `.trunk/trunk.yaml`
`ignore` list, test fixtures, response schema docstrings (they are API contract
text), and lint or type directives (`# noqa`, `# type: ignore`,
`eslint-disable`), whose dash separators are syntax. In embedded mode it edits
the PR description in the summary, keeping the AI disclosure and what
`review-polish` §F requires.

RomM rules win: rewritten text still meets `review-polish` §A, and a file's
existing headings and bold labels stay (skip "Bold as decoration" and
"Decorative headings" there). Then run `trunk fmt && trunk check` on the files
it touched.
