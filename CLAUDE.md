# RomM Frontend v2 — Constitution

This file governs work inside `frontend/src/v2/`. It is the canonical source of v2 working rules. Read it before editing v2 code.

> **Official language**: code, comments, identifiers, .md files, commit/PR messages — English. Always.

Full migration plan: `/home/ymir/.claude/plans/i-want-to-create-majestic-kazoo.md`.

---

## I. Premises

These are stable. They change only through explicit redesign.

1. **v1 is frozen.** v2 lives under `src/v2/`, gated by `user.ui_settings.uiVersion`. v1 (`src/views/`, `src/components/`, `src/console/`, `src/layouts/`) is not refactored — it will be deleted wholesale in the final wave.
2. **Three component tiers** (see §II). Primitives in `src/v2/lib/`, shared composites in `src/v2/components/shared/`, feature composites in `src/v2/components/<feature>/`.
3. **Shared resources are canonical.** Pinia stores, API services, OpenAPI types, locales, utils — v2 imports them; v2 does not fork them. Additive changes are allowed when v1 still uses them.
4. **Tokens are the only source of truth for theming.** No hex literals anywhere. If a value is missing a token, create the token.
5. **Dual theme is mandatory.** Every component must work in `v2-dark` and `v2-light`.
6. **Universal input.** All v2 UI works with mouse, touch, keyboard, and gamepad.
7. **Wrapper contract.** Wrappers around Vuetify components use `defineOptions({ inheritAttrs: false })` + `v-bind="$attrs"` + slot passthrough. They accept every prop/slot of the wrapped component.
8. **Universal substitution.** When an `R*` exists, it is used. If it doesn't exist, it is created or extended. Never drop to raw HTML elements or raw Vuetify when a primitive applies.
9. **Layout via Vuetify utility classes + our wrappers, not plain CSS.** Utility classes (`d-flex`, `pa-4`, `align-center`) are used directly. Vuetify's layout components (`v-row`, `v-col`, `v-container`, `v-spacer`, `v-app`, `v-main`) are wrapped as `R*` when used as components — wrap on first use (lazy).
10. **Storybook is mandatory for `/lib`.** Every primitive ships at least one story with controls.
11. **TypeScript strict.** Zero `any` (justified with comment otherwise). No `as unknown as ...` workarounds.
12. **Accessibility.** Semantic HTML, focus management, contrast, ARIA where needed.
13. **Performance.** Lazy-load heavy views. Virtualize large lists. Avoid unnecessary watchers/computeds. `v-for` always has a stable `:key`.

---

## II. lib vs components — three tiers

| Tier                  | Path                           | Prefix         | Stores / services / router / emitter / i18n | Story     | Domain knowledge                  |
| --------------------- | ------------------------------ | -------------- | ------------------------------------------- | --------- | --------------------------------- |
| **Primitive**         | `src/v2/lib/`                  | `R*` mandatory | **No**                                      | Mandatory | None                              |
| **Shared composite**  | `src/v2/components/shared/`    | no prefix      | Yes                                         | Optional  | Cross-feature, no specific domain |
| **Feature composite** | `src/v2/components/<feature>/` | no prefix      | Yes                                         | Optional  | Feature-specific                  |

### Decision criteria for primitive

A component is a primitive only if **all three** hold:

1. Does not depend on stores, services, router, or emitter.
2. No knowledge of a product domain (ROM, Platform, Collection, User…). `RAvatar` yes, `UserAvatar` no.
3. API can be described without naming features. Generic props/slots/events.

If any criterion fails: **shared composite** if it is generic across features, **feature composite** if it is owned by one feature.

### Primitive boundaries

- **Can use**: tokens, other primitives, Vue/Vuetify, generic composables (`useInput*`, `useFocus*`).
- **Cannot use**: Pinia stores, API services, `emitter`, `router` (except `RouterLink` accepted as a prop), `i18n` directly.
- **No `$t()` in primitives.** Text is always passed via props or slots.

### Folder structure

- Primitive: `RFoo/RFoo.vue`, `RFoo/RFoo.stories.ts`, `RFoo/index.ts`, optional `RFoo/types.ts`.
- Composite: flat `.vue` if a single file is enough; folder with the same internal structure (no story required) if it has sub-pieces.

### Barrel

- `src/v2/lib/index.ts` re-exports every primitive. Update when a new primitive ships.
- Composites are imported directly by path; no barrel.

### Promotion / demotion

If a component meets the three primitive criteria, it stays primitive regardless of consumer count. Edge cases get raised to the user, not auto-decided.

---

## III. Visual language

1. **Single visual vocabulary.** Every surface (dialog, menu, popover, card, toolbar) reads as a sibling — same blur, same curvature, same depth. No standalone "dialog look" vs "menu look".
2. **Canonical references when designing**: ask the user before consulting `https://mockup.thebirdcage.tv/`. They decide whether the mockup or existing primitives (`RDialog`, `RMenuPanel`, …) take priority.
3. **Tokens drive everything** (premise 4). If a value isn't in tokens, create the token.
4. **State semantics are shared across primitives**:
   - hover (neutral, or brand-tinted on selected rows)
   - selected/checked (`--r-color-brand-primary`)
   - active/favorite (`--r-color-fav`)
   - focus (modality-gated; visible only on `key`/`pad`)
   - busy/pending
   - disabled
     The set may grow; it does not get reinvented per component.
5. **Implementation gotchas worth keeping**:
   - `RDialog` ships unscoped `<style>` at the bottom that strips Vuetify defaults from `.v-overlay__content`. Load-bearing — without it the corners of `--r-radius-card` disappear.
   - Every dialog goes through `RDialog`. Every menu through `RMenu`.

---

## IV. Tokens & theming

### Source of truth

`src/v2/tokens/index.ts` is the source. It feeds two things:

- `src/v2/styles/tokens.css` — **generated** by `scripts/build-tokens.ts` (npm script `build:tokens`, hooked into `predev` and `prebuild`). Do not hand-edit.
- `src/v2/theme/vuetify.ts` — Vuetify theme registered as `v2-dark` / `v2-light`, derived from the same tokens.

Components consume tokens via `var(--r-color-...)` in CSS or via `color="primary"` in Vuetify (which reads the theme). **Never hex literal in components.**

### Adding a new token

1. Add to `src/v2/tokens/index.ts` with a semantic name (role-based: `--r-color-danger`, not `--r-color-red`).
2. Provide both dark **and** light values (premise 5).
3. If consumed via Vuetify's `color` prop, register in the Vuetify theme too.
4. Run `npm run build:tokens` to regenerate `tokens.css`.
5. If the JS path → CSS variable name needs an exception (special abbreviation like `--r-nav-h`), add an entry to `NAME_OVERRIDES` in the generator.

### Where scope classes live

`.r-v2`, `.r-v2-dark`, `.r-v2-light` go on `<html>`. `RomM.vue` toggles them on `document.documentElement` whenever `uiVersion` or the active theme changes.

Why `<html>` and not `<v-app>` or `AppLayout`: Vuetify teleports overlays (`VDialog`, `VMenu`, `VTooltip`) to `<body> > .v-overlay-container`, which is **outside** `<v-app>`. Only `<html>` covers both the regular tree and the teleports — without it, overlays lose their tokens.

### Diagnostics

When `var(--r-color-...)` resolves to nothing on an overlay:

1. Check `RomM.vue`'s watch on `documentElement.classList`. Load-bearing.
2. Check that the teleported component carries a `content-class` that ties it back to scope (e.g., `RDialog` uses `content-class="r-dialog"`).
3. **Never** "fix" by replacing the token with a hex literal — it hides the bug and breaks the dual theme.

---

## V. Universal input

### Origin

The input system started in `src/console/` (gamepad-only UI). v2 generalises it: it lives in `src/v2/composables/useInput/` (bus, keyboard, gamepad, actions, scope) and applies to all of v2. There are no `/console/*` routes in v2.

### Modality

`useInputModality` puts `data-input="mouse|touch|key|pad"` on `<html>` based on the most recent input.

- Focus rings appear only with `key` and `pad` (CSS in `global.css`).
- Hit targets may scale up for `touch` and `pad`.
- **Never use `:focus` directly in styles** — use the modality-gated selectors. Otherwise focus rings flash on mouse click.

### Coverage

Every interactive primitive participates in spatial navigation: buttons, list items, tabs, menu items, focusable cards, toggleable chips. Not optional.

A new interactive primitive must:

- be focusable (proper tabindex, or wrapped Vuetify component already is).
- react to logical actions (confirm/cancel) from `useInput`, in addition to native click.
- show a modality-gated focus state.

Storybook `play()` covering gamepad input is required **only when applicable** (the primitive is interactive enough that gamepad navigation actually matters).

### Focus geometry

Each view declares its layout using focus primitives: `RFocusZone`, `RFocusGrid`, `RFocusRow`, `RFocusColumn`. Multiple regions = multiple zones. Predictable up/down/left/right movement is the view's responsibility.

### Element-level global shortcuts

Above the per-view geometry, certain elements have dedicated bindings regardless of focus location:

- `UserMenu` opens on Start.
- Navbar tabs cycle with LB/RB (in addition to D-pad).
- Context menu opens on X or Y.

These bind globally, not per-view.

### Scope (overlay stack)

When a dialog opens, push a scope. When it closes, pop. This prevents Escape from closing two things at once and prevents `confirm` from leaking to controls beneath an overlay.

`RDialog` and `RMenu` handle their scope automatically. Custom overlays are an anti-pattern (premise 8) — go through the primitives.

### Responsive layout

Premise 6 (universal input) has a sibling: **universal viewport.** Every v2 surface must read cleanly from a 320px phone to a 4K display. The mechanism is fixed; do not invent a parallel one.

- **Single breakpoint source: `useBreakpoint`** (`src/v2/composables/useBreakpoint/`). Material thresholds — `xs <600`, `sm 600–959`, `md 960–1279`, `lg 1280–1919`, `xl ≥1920`. `installBreakpointAttribute()` (mounted once in `AppLayout`) mirrors the active set onto `<html data-bp="…">`.
- **Layout switches live in CSS** via the attribute selector: `html[data-bp~="xs"] .foo { … }`, `html[data-bp~="sm-and-down"] .foo { … }`. **No raw `@media` for layout** — the only allowed `@media` are `prefers-reduced-motion` and print. The attribute is on `<html>` so it reaches teleported overlays too.
- **Conditional rendering** (mount/unmount a different component per tier, not just restyle) uses the `useBreakpoint()` refs in `<script>` — e.g. `v-if="xs"`. Prefer mount-gating over `display:none` for focusable chrome so hidden controls never sit in the tab/spatial-nav order.
- **`--r-row-pad` is the global horizontal gutter** and is already re-scoped responsive in `global.css` (36 → 20 → 14px). Consume `var(--r-row-pad)`; don't hard-code a smaller `xs` padding per component.
- **Touch targets** ≥ `--r-touch-target` (44px) on `xs` / touch. Gate the bump to touch/pad where desktop sizing would bloat.
- **Overlays go full-bleed on `xs`.** `RDialog` renders as a full-screen / bottom sheet on phones (`fullscreenOnMobile`, default on); `RMenu` bottom-sheets large menus. Never float a 600px dialog on a 360px screen.
- **Label→icon collapse** (the AppNav precedent) is the canonical way to compress chrome; the four primary destinations relocate to `BottomNav` (bottom tab bar) on `sm-and-down`.
- **Grids** size via `useResponsiveColumns` (ResizeObserver), never a fixed column count.

Verification adds the breakpoint sweep — see §VII.6.

---

## VI. Architecture patterns

### A. Errors & snackbars

- Single channel: `useSnackbar()` (`src/v2/composables/useSnackbar/`) with `success | error | warning | info` methods. Internally emits `snackbarShow`; `NotificationHost` stacks toasts (improvement over v1's overwriting single snackbar).
- Canonical tones: `success | error | warning | info`. The current color-string collapser in `NotificationHost` is debt; remove when v1 dies.
- The call site emits — no global "wrap-every-promise" magic. Each feature decides what is significant.
- Field validation errors render in-place, never as a snackbar.
- Auth (401/403) is handled by the axios interceptor; no per-call-site checks.
- Successful critical actions: `success` snackbar. Routine optimistic toggles: silent on success, `error` on failure.

### B. Loading states

- **Skeleton** for first load of a view with known layout (`RSkeletonBlock`). The skeleton mimics the real shape so the layout doesn't jump on data arrival.
- **Inline `:loading` on the control itself** for actions in flight inside that control (`RBtn`, `RTextField`, `RSelect`). Never put an external `RSpinner` next to a button that has its own `loading`.
- **`RSpinner` inline** when what's loading is not a control with native `loading`.
- **Determinate progress (with %)**: build `RProgressLinear` when needed. Premise 8 — no raw `v-progress-linear`.
- **Empty state ≠ loading state.** Zero items is a distinct UX (message, illustration, optional CTA).
- **Optimistic toggles do not show spinners.** UI flips immediately; on failure, revert and snackbar.
- **Spinner debounce**: `RBtn` ships with `loadingDebounce={200}` by default — actions resolving under 200ms never paint a spinner. Going loading → not-loading is immediate.

### C. Real-time updates (Socket.IO)

- One instance: `src/services/socket.ts`. Never new `io()`.
- New consumers go through (or build) a `useSocketEvent(event, handler)` composable for typed subscriptions with automatic mount/unmount cleanup. Auto-connects if needed. _(Composable is debt — see §X.)_
- **Event map typed in one place** (deferred until backend exposes typed event catalog).
- **Ownership rule**: state living only while a view is open → `useSocketEvent` in the view. State that must outlive a view (e.g., scan badge in navbar) → a Pinia store subscribes globally; views just read.
- Reconnection is socket.io's job. Do not roll your own.

### D. UI state persistence

Three layers, decision rule per state:

1. **Persistent preferences** (theme, language, gallery defaults like `groupRoms`/`boxartStyle`, Home panels): `useUISettings` (localStorage + backend `user.ui_settings` two-way sync). Add a key to `UI_SETTINGS_KEYS`.
2. **Bookmarkable session state** (active filters, search query, sort, current tab in detail views): URL query params. Anyone copying the link reproduces what they see.
3. **Ephemeral session state** (open dialog, hover, expansion): `ref` if local, Pinia store if cross-component within session.

**Active gallery filter must be in URL** (rule). Migration of `stores/galleryFilter.ts` to URL-sync is debt — see §X.

### E. Pagination & infinite scroll

- `LoadMore` is the canonical fallback: `RBtn + RSpinner + IntersectionObserver`. Used as fallback when virtualization stalls.
- `RVirtualScroller` (wrapping `v-virtual-scroll`, primitive in `src/v2/lib/structural/`) is the substrate for large lists/grids. **Migration of `GameGrid` and `LetterGroupedGrid` is debt** — see §X.
- Page size lives in the store (`fetchLimit`); not user-configurable for now.
- **Scroll restoration** when navigating back: Vue Router `scrollBehavior` + Pinia keeps in-session offset. URL holds filters/sort/search but **not** scroll offset. Migration is debt — see §X.

### F. Forms & validation

- **`RForm` primitive** wrapping `v-form` with QoL: Enter on any field submits when valid, scroll-to-first-error after a failed `validate()`. Standard wrapper contract.
- **Native Vuetify rules** — no Zod/Yup. Rules are arrays of `(v) => true | string` functions.
- **Reusable rules** in `src/v2/utils/validation.ts` (`required(msg?)`, `email`, `asciiOnly`, `lengthBetween`, `usernameLength/Chars`, `passwordLength`). Utility code is allowed to call `i18n.global.t(...)` (the no-i18n rule covers lib primitives, not utils).
- **Submit pattern**:
  - `await formRef.value?.validate()` before calling the API.
  - Submit button uses `:loading="submitting"`.
  - Errors → snackbar; field errors stay in-place.
  - Backend field errors map to `:error-messages` per field. Format is debt — backend to formalise `{ field: msg }`.

### G. Permissions

- Action vocabulary: `domain.action` (e.g., `rom.upload`, `rom.delete`, `library.scan`, `user.create`, `app.admin`). Defined in `src/v2/composables/useCan/actions.ts`.
- Scope vocabulary:
  ```ts
  type PermissionScope =
    | { kind: "global" }
    | { kind: "platform"; id: number }
    | { kind: "collection"; id: number }
    | { kind: "rom"; id: number };
  ```
- **`useCan(action, scope?)`** returns `ComputedRef<boolean>`, reactive to `permissionsStore.grants`. Without scope: "can do this anywhere."
- **`stores/permissions.ts`** holds normalised grants. Today hydrated from `authStore.user.role` via the role-map (`installPermissionsHydration()` mounted in `AppLayout`); tomorrow served by `/permissions/me`.
- **`v-if`** to hide options a user shouldn't see; **`:disabled`** with tooltip when the option must be visible but blocked.
- **Backend is source of truth.** Frontend is UX hint. Never bypass with inline `user.role === "..."`.
- **No `useCanAsync`** — all grants are pre-loaded. If granularity reaches per-ROM ACLs, revisit.

### H. Destructive confirmations

Three friction levels:

- **Low** / **High**: shared composite `ConfirmDialog` (in `components/shared/`) opened via `useConfirm({ title, body, confirmText, tone, requireTyped }) => Promise<boolean>`. Mounted once in `GlobalDialogs`.
- **Medium**: feature composite when the destructive flow needs extra options (e.g., `DeleteRomDialog` with per-item filesystem checkboxes).

Common rules:

- All destruction goes through a dialog. No silent destructive action.
- Confirm button is danger-toned; **focus initially on Cancel**. Enter cancels.
- After success: success snackbar or navigate away; dialog closes.
- After error: error snackbar; dialog stays open.
- During action: confirm shows `:loading`; cancel disabled.
- The destructive control respects `useCan(action, scope)`.
- **No "don't ask again."** Every destructive action confirms.
- **Type-to-confirm (`requireTyped`) is required when the action affects filesystem.**

---

## VII. Verification before handoff

### Static — local + CI

1. `npm run typecheck` — zero errors.
2. `npm run lint` — zero errors. (`lint` is scoped to `./src/v2`; `lint:all` sweeps v1 too for visibility.)
3. `npm run test` — zero failures (Vitest 4 + happy-dom; runs unit tests _and_ every `/lib` story's `play()` via `composeStories`).
4. `npm run build` — zero failures (in CI, sanity check).

### Generated types

5. If you touched the backend API, run `npm run generate` and re-typecheck.

### UI (when changes are visible)

6. Browser test with `uiVersion = "v2"`: golden path + edge cases (empty, error, loading, no-permission, extreme data) + nearby regressions.
7. Both themes: dark and light.
8. All four input modalities: mouse, touch, keyboard, gamepad. Focus ring only on `key`/`pad`.
9. Accessibility minimum: contrast, keyboard reachability without traps, aria-labels for icon-only controls.

### Storybook

10. New primitive → mandatory story with controls and at least one variant per theme.
11. Modified primitive → existing story renders + interactions still pass.

### i18n

12. `en_US` is the source of truth, but **every key added to `en_US` must be added to all other locale directories in the same change** — never leave a key English-only. Translate where you can; otherwise copy the English value as a placeholder so the key exists. Run `python3 frontend/src/locales/check_i18n_locales.py` — it must pass with zero missing/extra keys (also enforced in CI via `i18n.yml`).
13. Never hard-code strings in user-visible components.

### Performance (when applicable)

14. Lists/grids with 1000+ items still smooth. Use `RVirtualScroller` once the gallery migration lands; until then, `LoadMore` keeps things working at smaller scales.
15. `v-for` always with a stable `:key` (not the index, except for trivial static lists).

### Tests

16. New logic in a composable / store / util → Vitest test.
17. New primitive → story + `play()` interaction (counts as interactive test).

### Anti-checklist

- Never open a PR without manually testing the UI when UI was touched. Static checks don't prove the feature works.
- Never `--no-verify` on commits.
- Never duplicate coverage between Vitest and Storybook play().

---

## VIII. Anti-patterns

Listed only when they go beyond what premises already say.

1. **Don't change shared store APIs to work around v2 call-site issues.** Lesson from the Gallery migration: the fix for `fetchingRoms` not resetting was calling `romsStore.reset()` from the v2 view, not adding `_fetchSeq` to the store. Stores are canonical; their API doesn't bend to one consumer.
2. **Don't "fix" an unresolved token by replacing it with a hex literal.** Diagnose scope on `<html>` instead.
3. **Don't use bare `:focus` in CSS.** Use the modality-gated selectors from `global.css`.
4. **Don't drop to inline role checks.** Always go through `useCan`.
5. **Don't snackbar every rejected promise.** 401/403 are interceptor-handled. Field errors are in-place. Only significant errors hit the snackbar — the call site judges.
6. **Don't push a state into `useUISettings` "so it persists."** Three-layer rule (D): bookmarkable → URL, persistent → useUISettings, ephemeral → ref/store.
7. **Don't reinvent a surface.** Dialog / menu / popover / card panel all go through their primitive. Special cases get a new prop on the primitive, not a parallel surface.
8. **Don't use `v-form` directly.** Use `RForm`.
9. **Don't add backwards-compat shims inside v2.** Delete removed code; no `// removed`, no renamed-but-unused exports, no deprecated wrappers that just call the new function.
10. **Don't write redundant tests.** Storybook `play()` covers components; Vitest covers pure logic. Don't repeat.
11. **Don't touch v1.** Premise 1 — repeated because the temptation is real once v2 imports from `src/stores/`.
12. **Mark v1 as `@deprecated` when a v2 equivalent exists.** When coexistence forces a v2 fork of a store/composable/util, annotate the v1 export with `@deprecated` pointing to the v2 replacement. Makes the v1 cleanup wave trivial to navigate.

### Allowed (because it's often misread)

- Modifying shared stores/services/utils **additively** is permitted. Premise 3 says "don't fork", not "don't touch."
- Creating a new v2-only composable when a v1 equivalent exists **is allowed.** Premise 3 covers stores/services/types/locales/utils. Composables can be v2-only (`useCan`, `useSnackbar`, `useConfirm`, `useWebpSupport`, …).
- Importing from `src/__generated__/` is canonical for v2 features.

---

## IX. File conventions

### Vue SFCs

- `<script setup lang="ts">` always.
- `defineOptions({ inheritAttrs: false })` on every wrapper, paired with `v-bind="$attrs"` and slot passthrough. Without the bind, attrs vanish silently.
- Props typed via `defineProps<Props>()` (interface), never runtime declarations.
- Emits typed via `defineEmits<{...}>()`.
- Slots with payload via `defineSlots<{}>()` (Vue 3.3+).
- Order: `<script setup>` → `<template>` → `<style scoped>`. Unscoped `<style>` (teleport overrides) goes after the scoped block.

### Imports

```ts
// 1. External
// 2. v2 primitives
import { RBtn, RDialog } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/__generated__";
import romApi from "@/services/api/rom";
// 5. Canonical shared resources
import storeAuth from "@/stores/auth";
// 4. v2 feature siblings
import GameCard from "@/v2/components/GameCard.vue";
import ConfirmDialog from "@/v2/components/shared/ConfirmDialog.vue";
// 3. v2 composables / shared
import { useCan } from "@/v2/composables/useCan";
```

Aliases:

- `@v2/lib` — primitives barrel.
- `@/v2/...` — anything else under v2.
- `@/...` — canonical shared resources.
- Never relative paths (`../../foo`) when an alias exists.

### Styles

- Scoped by default.
- Unscoped only for teleport overrides.
- BEM-ish: `.feature__element--modifier`.
- Class prefixes: `.r-v2-...` for surfaces outside components (app shell layers); `.r-...` for utilities/tokens shared globally.
- Zero hex literals (premise 4).
- Zero plain CSS where Vuetify utility classes cover the case (premise 9).

### TypeScript

- Strict (premise 11). Zero `any` except justified with comment.
- Zero `as unknown as ...`. Fix the source or define an intermediate type.
- `type` for unions/mappings; `interface` for shapes that get extended. Internal consistency, not holy war.
- Shared v2 types in `src/v2/types/`. Backend types from `src/__generated__/`. Not `src/types/` (legacy).

### Composables

- `use` prefix.
- Single named export from `composables/useFoo/index.ts`.
- Fully typed args and return.
- No side effects on module load. Init on first call.

### Console

- `console.error` allowed for production-visible errors.
- `console.log` / `console.warn` does not ship.
- `console.debug` allowed during development; remove before PR.

### Files

- One primitive per folder: `RFoo/RFoo.vue` + `RFoo/RFoo.stories.ts` + `RFoo/index.ts` (+ `types.ts` if needed).
- Composites: flat `.vue` if it fits one file; folder if sub-pieces.
- `index.ts` only in barrels. No single-file `index.ts` re-exports just to shorten import paths.

### Language

Code, comments, identifiers, .md files, commit/PR messages — English. Always.

---

## X. Known debt

The constitution is fully described above. The following implementation tasks remain. Tackle each as a focused PR with browser verification.

### Frontend debt

1. **Virtualisation migration** — `RVirtualScroller` primitive is in `src/v2/lib/structural/`. Migrating `GameGrid` and `LetterGroupedGrid` to use it requires structural refactor of `Platform.vue` / `Search.vue` / `Collection.vue` (single virtualiser owning the scroll, hero/toolbar/content/load-more all as virtual items via dynamic-height mode). `useLetterGroups` has to become index-based for AlphaStrip's scroll-spy to keep working. Without this, libraries beyond ~3k ROMs degrade.
2. **`useGalleryFilterUrl`** — sync galleryFilter store fields (search, multi-select selections, logic operators) to URL query params so links are bookmarkable. Decide which subset is bookmarkable; the v1 store stays as it is and the v2 composable mirrors it. Mark v1 store usage as `@deprecated`.
3. **Vue Router scroll restoration** — galleries scroll on custom containers (`.r-v2-plat__scroll`), not window. Add a Pinia map of `routeFullPath → offsetTop` plus per-view onMounted/onBeforeUnmount hooks to restore scroll on back navigation. Bundle with the virtualisation migration.
4. **`useSocketEvent` composable** — typed subscriptions with mount/unmount cleanup. Today consumers wire `socket.on/off` manually.

### Backend debt (frontend can't fix)

5. **`ActionKey` enum in OpenAPI** — eliminates the manual `actions.ts` + `role-map.ts` pair; the frontend regenerates and gets compile-time alignment.
6. **`/permissions/me` endpoint** returning normalised grants. Replaces `hydrateFromRole`; drops the role-map.
7. **`permissions:changed` socket event** for live grant updates.
8. **`FrontendDict.IMAGES_WEBP`** in OpenAPI — drops the cast inside `useWebpSupport`.
9. **Form error format** standardised as `{ field: msg }` so `RTextField :error-messages` integration is consistent.
10. **Typed socket event map** from the backend so the eventual `useSocketEvent` composable is fully typed.

### When v1 is deleted

11. Move `uiVersion` from `useUiVersion` into `UI_SETTINGS_KEYS`.
12. Drop `.r-v2-...` scope classes; tokens move to `:root`.
13. Simplify `useUISettings` sync (remove `isSyncing` + `setTimeout(50)` flag-flip).
14. Delete `useGameAnimation` (replaced by view transitions, premise 8 era).
15. Drop the color-string-to-tone collapser in `NotificationHost`; `snackbarShow` payload becomes `{ msg, tone, ... }`.
16. Remove the Vuetify rule arrays in `stores/users.ts` once v1 doesn't consume them; v2 already composes from `src/v2/utils/validation.ts`.

### Color-literal policy: zero exceptions

Outside `src/v2/tokens/index.ts` (the source-of-truth TS module) and the generated `src/v2/styles/tokens.css`, **no hex or `rgba()` literals exist anywhere in v2**. Premise 4 is enforced; the previous "intentional exceptions" list has been collapsed into tokens:

- Cover-overlay glass → `--r-color-overlay-*` (fixed dark glass; never theme-flips).
- Cover artwork placeholder & shimmer → `--r-color-cover-placeholder`, `--r-color-cover-placeholder-bright`.
- Panel / tooltip / shimmer-sweep → `--r-color-panel`, `--r-color-panel-border`, `--r-color-tooltip-bg`, `--r-color-shimmer-sweep` (paired dark/light values).
- Backdrop scrims in `global.css` → `color-mix(in srgb, var(--r-color-bg) X%, transparent)` (inherits the theme's base bg).
- Status tints (success/warning/danger/info backgrounds, borders) → `color-mix(in srgb, var(--r-color-status-base-{success,warning,danger,info}) X%, transparent)`.
- Brand-tinted backgrounds (selected rows, focus rings) → `color-mix(in srgb, var(--r-color-brand-primary) X%, transparent)`.
- Black/white shadows → `color-mix(in srgb, black X%, transparent)` (CSS named colour, not a hex literal).
- Metadata-provider chips → `--r-color-provider-*`.
- Player canvas → `--r-color-canvas-bg`, `--r-color-canvas-bg-deep`.
- Emphasis pill (always-white-on-dark "Play" CTA over cover art) → `--r-color-overlay-emphasis-bg/-fg/-bg-hover`.

If a literal would otherwise be needed, the answer is: **add a token**. Update `src/v2/tokens/index.ts`, run `npm run build:tokens`, then consume via `var(--r-color-...)` (CSS) or by importing the named export (TS/JS — e.g., `colorCanvas`, `colorOverlay`).
