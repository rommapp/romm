---
name: review-polish
description: The self-review pass that catches what a RomM maintainer would otherwise rewrite by hand after approving a PR. Covers comment and docstring discipline (the single most-corrected thing in this repo), duplicated constants/types/getters, imprecise names, and loose typing in tests. Use after the code works and before requesting review, and whenever writing a comment, docstring, or a second copy of a value. Complements `pre-pr-verification`, which runs the checks; this one shapes the code the checks can't see.
---

# RomM: Review Polish

Derived from the corrections a maintainer actually pushed on top of 37 approved
contributor PRs. Every rule below is something that got hand-fixed after review,
so applying it up front saves a round trip.

Run this pass when the change works and the tests pass, before asking for review.

---

## A. Comments and docstrings: the most-corrected thing in this repo

`CLAUDE.md` already says keep comments short, don't restate the code, don't
explain a change. In practice contributions still ship multi-paragraph
rationale, and it gets cut. Cut it yourself.

**Hard limits.** A comment is one or two lines. A docstring is one sentence plus
an `Args:`/`Returns:` block when the signature needs it. If you wrote three or
more lines of prose, you are explaining, not commenting.

**Delete outright:**

- **Change history and migration notes.** "Replaces the manual pattern: ...",
  "this was dropped in 06cafd4b1", "gating it on the ENABLE_SCHEDULED_* flags
  left those jobs queued". The comment describes what the code does now. Reasons
  for the change belong in the commit message and the PR body.
- **Restatements of the adjacent line.** A `withTotal?: boolean` field does not
  need `// Skip the result-set count server-side`. An index named
  `idx_roms_missing_from_fs` does not need `# Serves the Missing tab`.
- **Defences of an obvious choice.** "so oversized input is rejected by
  validation instead of by the database", "these are the identifiers a user
  already knows a platform by".
- **Comparisons to the alternative you didn't pick.** "VueUse's `useMounted` is
  not a substitute because ...", "not worth rewriting".
- **The product name as the actor.** Write "before unfetched media paths were
  cleared", not "before RomM cleared unfetched media paths".

**Keep** the one non-obvious fact a reader cannot recover from the code: a
provider's undocumented behaviour, a cross-file invariant, a deliberate
fail-safe. One line.

```python
# ScreenScraper answers a refused credential set with a 200 and this marker in
# the body, so the text is checked before the status.
LOGIN_ERROR_CHECK: Final = "Erreur de login"
```

**This applies to Markdown too.** Doc tables and architecture notes get trimmed
the same way. A `KIOSK_MODE` row reads `Read-only anonymous access`, not that
plus a parenthetical about what logged-in accounts keep.

**User-facing copy is not a comment, but it gets the same precision pass.**
"midnight French time" became "midnight CET".

---

## B. One home per value: no second copy

The second most-corrected pattern. Before you declare a constant, type, limit,
regex, or store getter, search for it. If it exists, import it.

- **Limits live on the model, endpoints import them.** A
  `PLAYLIST_NAME_MAX_LENGTH = 400` in `endpoints/` duplicating the column width
  is wrong; export it from `models/` and import. While there, check the sibling
  field actually has its `max_length` too.
- **A type declared in the component that owns it gets exported.** Don't
  re-declare `type Kind = "regular" | "smart"` in a second SFC. Export it from
  the owner and import it.
- **One list feeding two patterns.** The article list behind both the sort key
  and LaunchBox's inverted-title regex is a single `ARTICLES` tuple that both
  regexes are built from.
- **Don't add a store getter that differs from an existing one only by
  sorting.** Fix the existing one instead. A near-duplicate getter usually means
  the original sorts on the wrong field (`name` where the UI shows
  `display_name`).
- **A repeated inline branch becomes a named helper with its own unit test.**
  Pull the cover-url fallback or the page-total resolution out, then test the
  helper directly.

**Do not over-extract.** A literal used once, whose meaning is plain at the call
site, stays inline. Naming every string is its own kind of noise, and it gets
trimmed too.

---

## C. Reuse the existing mechanism before inventing one

- **Use the existing foreign key.** A durable-reference scheme of your own
  (`(rom_id, md5_hash)` because file ids churn on rescan) loses to
  `rom_file_id` with `ondelete="CASCADE"`. If the real problem is churn, fix the
  churn.
- **Reach for VueUse before hand-rolling.** Persisted UI state is
  `useLocalStorage(key, default, { writeDefaults: false, serializer })`, not a
  `ref` plus a `watch` plus `localStorage.setItem`.
- **Put display logic on the component that renders it.** A bespoke
  `ratingChips` computed in a tab belongs in the card component and its
  `providers.ts` config.
- **Prefer a spread over mutate-after-construct.**
  `{ ...(x !== undefined ? { x } : {}) }` over building an object then
  conditionally assigning.

---

## D. Names say what the thing does

- `syncRom` renamed to `syncCachedRom`: it updates the cache, it does not fetch.
- Sort on `display_name` when `display_name` is what the user sees.

If a reviewer has to open the body to learn what a function touches, the name is
short a word.

---

## E. Tests: strict typing is part of the test

Trunk runs mypy over `backend/tests/`, and `vue-tsc` covers frontend tests. Both
catch these, but only after the contributor has handed the PR over.

- **Narrow optionals before attribute access.** `mock.await_args` is
  `X | None`; bind it and `assert ... is not None` first.
- **Build fixtures with a typed factory,** not a bare object literal cast:
  `function rom(overrides: Partial<DetailedRom> = {}): DetailedRom`.
- **Fakes need real signatures.** Subclass the type the code actually receives
  (`io.BytesIO`, not `io.RawIOBase`) and annotate the override.
- **Vue component mocks use the object `props` form**, since ESLint's Vue rules
  reject the array shorthand:
  `props: { label: { type: String, default: "" } }`.
- **Test through the path production uses.** If the endpoint moved to
  `get_roms_scalar(smart_collection_id=...)`, the test calls that, not the
  internal handler the endpoint no longer touches.

---

## F. Async and reactive lifecycle (v2)

See `frontend-v2-patterns` for the full set. The three that get fixed in review:

1. **Snapshot any reactive value a decision depends on before the first
   `await`.** The selection and the collection's `rom_ids` both move while
   requests are in flight, so `const wasAllFavorited = allFavorited.value` comes
   before the call, not after.
2. **Watch the narrowest source.** Watching `authStore.user` refires on every
   unrelated profile update; watch a derived primitive
   (`user?.oauth_scopes.includes("tasks.run") ? user.id : null`) so the
   watch is self-guarding and no manual "already ran for this id" flag is
   needed.
3. **Guard late resolutions with `useIsAlive()`** rather than a local
   `unmounted` flag and `onBeforeUnmount`.

---

## Checklist

- [ ] No comment or docstring over two lines of prose; no change history, no
      restatement, no justification of the obvious
- [ ] Every new constant, type, limit, and getter searched for first
- [ ] No new mechanism where an FK, a VueUse composable, or an existing
      component already does it
- [ ] Names say what the code touches
- [ ] Tests typecheck strictly and exercise the production path
- [ ] Reactive values snapshotted before `await`; watches on narrow sources
- [ ] `trunk fmt && trunk check` clean (see `pre-pr-verification`)
