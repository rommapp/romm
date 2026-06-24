---
name: frontend-i18n
description: Internationalization for the RomM frontend (both v1 and v2). Use whenever adding, renaming, or removing any user-visible string / translation key under frontend/src/locales/. Covers the en_US-is-source rule, the requirement to add every new key to ALL locale directories in the same change, namespace layout, and the check_i18n_locales.py validator enforced in CI. Trigger on any change to frontend/src/locales/**.
---

# RomM Frontend — i18n / Localization

User-visible strings are **never hard-coded** in components — they come from locale files via `vue-i18n` (`$t(...)` in templates/composites; utils may call `i18n.global.t(...)`; **v2 lib primitives must not call `$t` at all** — text passes via props/slots).

## Structure

- Locales live in `frontend/src/locales/<locale>/<namespace>.json`, loaded by dynamic glob import in `src/locales/index.ts`.
- **18 locales**: `en_US` (default + fallback), `en_GB`, `bg_BG`, `cs_CZ`, `de_DE`, `es_ES`, `fr_FR`, `hu_HU`, `it_IT`, `ja_JP`, `ko_KR`, `pl_PL`, `pt_BR`, `ro_RO`, `ru_RU`, `zh_CN`, `zh_TW`.
- Namespaces are per-feature files (e.g. `collection`, `common`, `console`, `detail`, `emulator`, `gallery`, `home`, `library`, `login`, `navigation`, `patcher`, `platform`, `scan`, `settings`, `task`).

## The rule (enforced in CI)

- **`en_US` is the source of truth**, but **every key added to `en_US` must be added to all other locale directories in the same change.** Never leave a key English-only.
- Translate where you can; otherwise copy the English value as a placeholder so the key exists.
- Removing or renaming a key means doing it across **every** locale.

## Verify before handoff

```bash
python3 frontend/src/locales/check_i18n_locales.py
```

It compares every non-English locale against `en_US` and **fails on any missing file, missing key, or extra key**. CI runs the same script (`.github/workflows/i18n.yml`) on any change under `frontend/src/locales/**`. It must pass with zero missing/extra keys.

## Adding a new language

Create a new folder under `frontend/src/locales/` mirroring `en_US/`'s files, then translate. Open the PR against `master` (see the docs/Contributing flow). This is the one i18n change where a new locale directory is expected.
