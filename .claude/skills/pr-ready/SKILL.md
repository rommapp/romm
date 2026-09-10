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
git fetch origin master

case "$ARGUMENTS" in
"") TARGET="$(git rev-parse HEAD)" ;;
# a pull ref needs its own refspec, the fetch above will not create it
*[!0-9]*) git fetch origin "$ARGUMENTS" && TARGET="$(git rev-parse FETCH_HEAD)" ;;
*) git fetch origin "pull/$ARGUMENTS/head" && TARGET="$(git rev-parse FETCH_HEAD)" ;;
esac

test -n "$TARGET" || { echo "cannot resolve target: $ARGUMENTS" >&2; exit 1; }
RANGE="$(git merge-base origin/master "$TARGET")..$TARGET"
```

An all-digit argument is a PR number, anything else is a branch. Stop if the
target does not resolve; do not fall through to a range built without it.

Steps 2 to 4 write to the working tree, so check the target out before running
them when it is not already the current branch.

When the target is the current branch, uncommitted work counts as part of the
change under review. Commit or stash anything unrelated first, so each step's
edits stay attributable.

## Steps

1. **`security-audit`** over `$RANGE`. Read-only. Stop only on a `malicious`
   verdict; `needs attention` is a finding for step 2.
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
