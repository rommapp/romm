---
name: pr-ready
description: Run the pre-submit gauntlet (security-audit, code-review, simplify, review-polish) over a change before opening or merging a PR.
argument-hint: "[PR number | branch | nothing for the current branch]"
disable-model-invocation: true
---

# PR-ready gauntlet

Run the four review passes RomM applies to every non-trivial PR, in this order,
over one fixed range. Do not skip a step or reorder them.

## Target

`$ARGUMENTS` is a PR number, a branch, or nothing (the current branch). Resolve
it to a fetched target and derive `$RANGE` before step 1, then reuse `$RANGE`
for every step. `HEAD` is the right target only when `$ARGUMENTS` is empty, so
run the dispatch rather than assuming it: skip it and all four passes review the
current checkout instead of what was asked for.

```bash
set -eu

git fetch origin master

case "$ARGUMENTS" in
"") TARGET="$(git rev-parse HEAD)" ;;
# a pull ref needs its own refspec, the fetch above will not create it
*[!0-9]*) git fetch origin "$ARGUMENTS"; TARGET="$(git rev-parse FETCH_HEAD)" ;;
*) git fetch origin "pull/$ARGUMENTS/head"; TARGET="$(git rev-parse FETCH_HEAD)" ;;
esac

RANGE="$(git merge-base origin/master "$TARGET")..$TARGET"
```

An all-digit argument is a PR number, anything else is a branch.

`set -e` is load-bearing here, because each failure otherwise fails open. A base
fetch that dies on the network, an argument that resolves to nothing, a missing
merge base: each leaves a side of `$RANGE` empty, and git reads an empty side as
`HEAD`, so `..$TARGET` is a valid range over the wrong commits rather than an
error. Abort on the first failure instead of handing four passes a range built
without the thing you asked them to review.

## Before steps 2 to 4

Step 1 is read-only and runs against `$RANGE` from wherever you are. The rest
are not: they rewrite files and run the repository's own code from the target
ref, including test runners, builds, `trunk`, package lifecycle scripts, and git
hooks. A clean step 1 verdict is no substitute for that, since an audit can miss
what it is looking for. So run steps 2 to 4 only on a ref you trust. On anything
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
work counts as part of the change under review: commit or stash anything
unrelated first, so each step's edits stay attributable.

## Steps

1. **`security-audit`** over `$RANGE`. Read-only. Stop on a `malicious`
   verdict; `needs attention` is a finding for step 2, not a stop.
2. **`code-review` at `xhigh` with `--fix`**, targeting the resolved target
   rather than "the current diff", so it sees the whole change.
3. **`simplify`**, after the correctness fixes so it can simplify those too.
4. **`review-polish`** last: its verification gate has to cover everything the
   earlier steps rewrote, and `trunk fmt` has to run after the final edit.

Commit after each step that changes files, naming the step in the message. A bad
automated fix is then one `git revert` away instead of tangled with three other
passes.

Finish with one consolidated summary rather than four transcripts: the security
verdict, what steps 2 and 3 changed by area, which checks ran and their results,
and anything still needing a human decision.

Four passes in one session is a lot of context. For a very large diff, run the
steps in separate sessions against the same `$RANGE`.
