---
description: Run the full pre-submit gauntlet (security-audit, code-review, simplify, review-polish) over a change before opening or merging a PR.
argument-hint: "[PR number | branch | nothing for the current branch]"
---

# PR-ready gauntlet

Run the four review passes RomM applies to every non-trivial PR, in this exact
order, over one fixed range. Do not skip a step, do not reorder them, and do not
stop early because an earlier step came back clean.

## Target

`$ARGUMENTS` names what to review: a PR number, a branch, or nothing (the
current branch). Resolve it once, up front, and reuse it for every step:

```bash
git fetch origin master
RANGE="$(git merge-base origin/master HEAD)..HEAD"   # or origin/pull/<n>/head for a PR number
git diff --stat $RANGE | tail -30
```

Uncommitted work in the tree counts as part of the change under review. Commit
or stash anything unrelated first, so each step's edits stay attributable.

## Steps

1. **`security-audit`** over `$RANGE`. Read-only. If the verdict is `malicious`,
   stop the gauntlet and report; a `needs attention` verdict is a finding to fix
   in step 2, not a reason to stop.
2. **`code-review` at `xhigh` with `--fix`**, targeting the branch (not "the
   current diff"), so it reviews the whole change rather than only what later
   steps have already touched.
3. **`simplify`**. Quality only, so it runs after correctness fixes have landed
   and can simplify them too.
4. **`review-polish`**. Last, because it both shapes comments/naming and runs
   the verification gate (`typecheck`/`test`/`build`, `pytest`, i18n, tokens,
   OpenAPI regen, `trunk fmt && trunk check`) over everything the previous steps
   changed. Its checks are the ones CI runs, so a green pass here is the point
   of the whole sequence.

Commit after each step that changed files, naming the step in the message. A
bad automated fix is then one `git revert` away instead of tangled with three
other passes.

## Report

One consolidated summary at the end, not four transcripts:

- Security verdict and anything it flagged.
- What `code-review --fix` and `simplify` actually changed, by area.
- Which verification checks ran and their results, plus any the diff made
  irrelevant (say which, and why).
- Anything still open that needs a human decision.

## Notes

- Four passes in one session is a lot of context. For a very large diff, run the
  steps in separate sessions against the same `$RANGE`.
- Static checks do not prove a feature works. When UI changed, `review-polish`
  still expects the manual browser pass (both themes, all four input
  modalities).
- Never `--no-verify`, and never commit around a failing check.
- AI assistance stays disclosed in the PR body per `CONTRIBUTING.md`, including
  when these passes wrote the fixes.
