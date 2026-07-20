---
name: frontend-i18n
description: Internationalization for the RomM frontend (both v1 and v2). Use whenever adding, renaming, or removing any user-visible string / translation key under frontend/src/locales/. Covers the en_US-is-source rule, the requirement to add every new key to ALL locale directories in the same change, namespace layout, and the check_i18n_locales.py validator enforced in CI. Trigger on any change to frontend/src/locales/**.
---

# RomM Frontend — i18n / Localization

User-visible strings are **never hard-coded** in components — they come from locale files via `vue-i18n` (`$t(...)` in templates/composites; utils may call `i18n.global.t(...)`; **v2 lib primitives must not call `$t` at all** — text passes via props/slots).

## Structure

- Locales live in `frontend/src/locales/<locale>/<namespace>.json`, loaded by dynamic glob import in `src/locales/index.ts`.
- **18 locales**: `en_US` (default + fallback), `en_GB`, `bg_BG`, `cs_CZ`, `de_DE`, `es_ES`, `fr_FR`, `hu_HU`, `it_IT`, `ja_JP`, `ko_KR`, `pl_PL`, `pt_BR`, `ro_RO`, `ru_RU`, `tr_TR`, `zh_CN`, `zh_TW`.
- Namespaces are per-feature files (e.g. `collection`, `common`, `console`, `detail`, `emulator`, `gallery`, `home`, `library`, `login`, `navigation`, `patcher`, `platform`, `scan`, `settings`, `task`).

## The rule (enforced in CI)

- **`en_US` is the source of truth**, but **every key added to `en_US` must be added to all other locale directories in the same change.** Never leave a key English-only.
- **Actually translate the value into each locale's language** — never paste English into non-English locales.
- Editing an existing string counts: changing `en_US` means re-translating that key in every other locale.
- Reuse each locale's established terms — grep a sibling key for how it renders "metadata", "provider", etc.
- Copying the English value is a last-resort placeholder, only when no translation is available, and must be flagged to revisit.
- Removing or renaming a key means doing it across **every** locale.

## Verify before handoff

```bash
python3 frontend/src/locales/check_i18n_locales.py
python3 frontend/src/locales/check_i18n_sorted.py   # add --fix to auto-sort
```

`check_i18n_locales.py` compares every non-English locale against `en_US` and **fails on any missing file, missing key, or extra key**. `check_i18n_sorted.py` **fails if any locale JSON file's keys aren't sorted alphabetically** (run with `--fix` to sort them in place). CI runs both scripts (`.github/workflows/i18n.yml`) on any change under `frontend/src/locales/**`; both must pass.

## Adding a new language

Create a new folder under `frontend/src/locales/` mirroring `en_US/`'s files, then translate. Open the PR against `master` (see the docs/Contributing flow). This is the one i18n change where a new locale directory is expected.
