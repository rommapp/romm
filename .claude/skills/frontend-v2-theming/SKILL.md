---
name: frontend-v2-theming
description: Theming, design tokens, colors, and visual language in the RomM v2 frontend. Use when styling v2 components, picking colors, adding/using CSS variables, working with light/dark themes, or whenever you'd reach for a hex/rgba literal. Covers the token pipeline (src/v2/tokens/index.ts → build:tokens → tokens.css), the .r-v2 scope classes, the zero-hex-literal policy, and shared state semantics. Trigger on any color/theme/token work under frontend/src/v2/.
---

# RomM v2 — Tokens, Theming & Visual Language

**Tokens are the only source of truth for theming. Zero hex/`rgba()` literals in v2 components.** If a value is missing, add a token. Every component must work in both `v2-dark` and `v2-light`.

---

## Token pipeline

`src/v2/tokens/index.ts` is the source. It feeds two consumers:

- **`src/v2/styles/tokens.css`** — _generated_ by `scripts/build-tokens.ts` (`npm run build:tokens`, hooked into `predev`/`prebuild`). **Do not hand-edit.** This is how the vast majority of tokens are consumed: `var(--r-color-...)` in CSS.
- **Direct JS/TS imports** of named exports (`colorCanvas`, `colorCoverArt`, `layout`, …) for the few cases needing a token value in JavaScript — baking colors into an SVG string (`utils/covers`), canvas/QR backgrounds (`Player/Ruffle.vue`, `ShowQRCodeDialog`), and the virtualiser's pixel math (`Gallery/listColumns` reading `layout`).

v2 has **no Vuetify theme of its own**, and no Vuetify at all. `tokens.css` emits a palette block per theme under `.r-v2.r-v2-dark` / `.r-v2.r-v2-light`; `RomM.vue` toggles those classes on `<html>`. v2 surfaces never read Vuetify's runtime theme (`src/plugins/vuetify.ts` serves v1 only).

### Adding a new token

1. Add it to `src/v2/tokens/index.ts` with a **semantic, role-based** name (`--r-color-danger`, not `--r-color-red`).
2. Provide **both** dark and light values.
3. Consume via `var(--r-...)` (CSS) or the named export (JS).
4. Run `npm run build:tokens` to regenerate `tokens.css`.
5. If the JS→CSS variable name needs an exception (e.g. `--r-nav-h`), add an entry to `NAME_OVERRIDES` in the generator.

### Where the scope classes live — and why `<html>`

`.r-v2`, `.r-v2-dark`, `.r-v2-light` go on `<html>` (`RomM.vue` toggles them whenever `uiVersion` or the active theme changes). The overlay primitives (`RDialog`, `RMenu`, `RTooltip`) `<Teleport to="body">`, landing **outside** the app root. Only `<html>` covers both the regular tree and the teleports; without it, overlays lose their tokens.

### Diagnostics — when `var(--r-color-...)` resolves to nothing on an overlay

1. Check `RomM.vue`'s watch on `documentElement.classList` (load-bearing).
2. Check that the overlay still teleports to `body`. A teleport to any other target can land outside the `<html>` scope.
3. **Never** "fix" it by swapping the token for a hex literal — that hides the bug and breaks the dual theme.

---

## Visual language

1. **Single visual vocabulary.** Every surface (dialog, menu, popover, card, toolbar) reads as a sibling — same blur, curvature, depth. No standalone "dialog look" vs "menu look".
2. **Canonical references when designing**: ask the user before consulting `https://mockup.thebirdcage.tv/`. They decide whether the mockup or existing primitives take priority.
3. **State semantics are shared across primitives** (don't reinvent per component):
   - hover (neutral, or brand-tinted on selected rows)
   - selected/checked (`--r-color-brand-primary`)
   - active/favorite (`--r-color-fav`)
   - focus (modality-gated; visible only on `key`/`pad` — see `frontend-v2-input`)
   - busy/pending · disabled
4. **Implementation gotchas:**
   - Every dialog goes through `RDialog`; every menu through `RMenu`; every tooltip through `RTooltip`. Each owns its teleport and positioning, so don't hand-roll a parallel surface. The scrim and the reference-counted body scroll lock (`lib/overlays/bodyScrollLock.ts`) belong to `RDialog` and `RDrawer` only; menus and tooltips have neither.

---

## Color-literal policy: zero exceptions

Outside `src/v2/tokens/index.ts` (the source-of-truth TS module) and the generated `src/v2/styles/tokens.css`, **no hex or `rgba()` literals exist anywhere in v2.** Everything previously "excepted" is now a token or a `color-mix`:

- Cover-overlay glass → `--r-color-overlay-*` (fixed dark glass; never theme-flips).
- Cover artwork placeholder & shimmer → `--r-color-cover-placeholder`, `--r-color-cover-placeholder-bright`.
- Panel / tooltip / shimmer-sweep → `--r-color-panel`, `--r-color-panel-border`, `--r-color-tooltip-bg`, `--r-color-shimmer-sweep`.
- Backdrop scrims (`global.css`) → `color-mix(in srgb, var(--r-color-bg) X%, transparent)`.
- Status tints → `color-mix(in srgb, var(--r-color-status-base-{success,warning,danger,info}) X%, transparent)`.
- Brand-tinted backgrounds (selected rows, focus rings) → `color-mix(in srgb, var(--r-color-brand-primary) X%, transparent)`.
- Black/white shadows → `color-mix(in srgb, black X%, transparent)` (CSS named color, not a hex literal).
- Metadata-provider chips → `--r-color-provider-*`. Player canvas → `--r-color-canvas-bg`, `--r-color-canvas-bg-deep`.
- Emphasis pill (always-white-on-dark "Play" CTA over cover art) → `--r-color-overlay-emphasis-bg/-fg/-bg-hover`.

If a literal would otherwise be needed, the answer is: **add a token** (steps above), then consume via `var(--r-color-...)` or the named export.

## Style conventions

- Scoped `<style>` by default; unscoped only for teleport overrides.
- BEM-ish class names: `.feature__element--modifier`. Prefixes: `.r-v2-...` for app-shell surfaces outside components; `.r-...` for globally shared utilities/tokens.
- No utility-class framework (no Tailwind, no Vuetify): layout is plain CSS in the component's scoped block, with tokens (`var(--r-space-*)`, `var(--r-radius-*)`) for every value that has one.
