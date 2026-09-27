---
name: pr-ready
description: Run the pre-submit gauntlet (security-audit, code-review, simplify, review-polish, humanizer) over a change before opening or merging a PR.
argument-hint: "[PR number | branch | nothing for the current branch]"
disable-model-invocation: true
---

# PR-ready gauntlet

Run the five review passes RomM applies to every non-trivial PR, in this order,
over one fixed range. Do not skip a step or reorder them.

## Target

`$ARGUMENTS` is a PR number, a branch, or nothing (the current branch). Resolve
it to a fetched target and derive `$RANGE` before step 1, then reuse `$RANGE`
for every step. `HEAD` is the right target only when `$ARGUMENTS` is empty, so
run the dispatch rather than assuming it: skip it and all five passes review the
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
error. Abort on the first failure instead of handing five passes a range built
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
work counts as part of the change under review: commit or stash anything
unrelated first, so each step's edits stay attributable.

## Steps

1. **`security-audit`** over `$RANGE`. Read-only. Stop on a `malicious`
   verdict; `needs attention` is a finding for step 2, not a stop.
2. **`code-review` at `xhigh` with `--fix`**, targeting the resolved target
   rather than "the current diff", so it sees the whole change.
3. **`simplify`**, after the correctness fixes so it can simplify those too.
4. **`review-polish`**: its verification gate has to cover everything the
   earlier steps rewrote.
5. **`humanizer`** last, in file mode, over the prose `$RANGE` adds or changes:
   Markdown files, and comments and docstrings on added lines. It skips string
   literals, locale files, generated and vendored paths, and test fixtures. Run
   it in embedded mode on the PR description in the summary too, keeping the AI
   disclosure and the template headings. Two RomM rules win over its patterns:
   a rewritten comment still meets `review-polish` §A, so cut rather than
   lengthen, and a file's existing headings and bold labels are its house style,
   so §19 and §20 apply only where new prose breaks that style. It edits only
   prose, so re-run `trunk fmt && trunk check` on the files it touched instead
   of the full gate.

Commit after each step that changes files, naming the step in the message. A bad
automated fix is then one `git revert` away instead of tangled with four other
passes.

Finish with one consolidated summary rather than five transcripts: the security
verdict, what steps 2, 3 and 5 changed by area, which checks ran and their results,
and anything still needing a human decision.

The summary also carries what the PR description needs and the transcripts hold: the
screenshots step 4 captured, which the PR body references and `gh ... --attach` uploads
under the `Screenshots` heading, and the `mermaid` block for a change that moved a
boundary.

Five passes in one session is a lot of context. For a very large diff, run the
steps in separate sessions against the same `$RANGE`.
