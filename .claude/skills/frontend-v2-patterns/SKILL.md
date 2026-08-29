---
name: frontend-v2-patterns
description: Cross-cutting feature patterns for the RomM v2 frontend — error/snackbar handling, loading & skeleton states, real-time Socket.IO updates, UI state persistence (URL vs localStorage vs ephemeral), pagination/infinite scroll, forms & validation, permissions (useCan), and destructive confirmations. Use when wiring up a v2 feature's behavior (not just its markup). Trigger when implementing data flows, dialogs, forms, toggles, or permission gating under frontend/src/v2/.
---

# RomM v2 — Architecture Patterns

How v2 features behave. Each pattern has one canonical mechanism — don't invent a parallel one.

---

## A. Errors & snackbars

- Single channel: `useSnackbar()` (`src/v2/composables/useSnackbar/`) with `success | error | warning | info` methods. It emits `snackbarShow`; `NotificationHost` stacks toasts.
- The **call site** decides what's significant — no global "wrap-every-promise" magic.
- Field validation errors render **in-place**, never as a snackbar.
- Auth (401/403) is handled by the axios interceptor; no per-call-site checks.
- Successful critical actions → `success` snackbar. Routine optimistic toggles → silent on success, `error` on failure.
- Don't snackbar every rejected promise.

## B. Loading states

- **Skeleton** (`RSkeletonBlock`) for first load of a view with known layout — mimic the real shape so the layout doesn't jump.
- **Inline `:loading` on the control itself** for in-flight actions (`RBtn`, `RTextField`, `RSelect`). Never put an external `RSpinner` next to a button that has its own `loading`.
- **`RSpinner` inline** when what's loading isn't a control with native `loading`.
- **Determinate progress (%)**: use `RProgressLinear` — no raw `v-progress-linear`.
- **Empty state ≠ loading state.** Zero items is its own UX (message, illustration, optional CTA).
- **Optimistic toggles show no spinner**: flip immediately; on failure, revert + snackbar.
- `RBtn` ships `loadingDebounce={200}` — actions resolving under 200ms never paint a spinner; loading→not-loading is immediate.

## C. Real-time updates (Socket.IO)

- One instance: `src/services/socket.ts`. Never `new io()`.
- New consumers go through (or build) a `useSocketEvent(event, handler)` composable for typed subscriptions with automatic mount/unmount cleanup (this composable is still debt — today consumers wire `socket.on/off` by hand).
- **Ownership rule:** state living only while a view is open → subscribe in the view; state that must outlive a view (e.g. scan badge in navbar) → a Pinia store subscribes globally and views just read.
- Reconnection is socket.io's job — don't roll your own.

## D. UI state persistence — three layers

1. **Persistent preferences** (theme, language, gallery defaults like `groupRoms`/`boxartStyle`, Home panels) → `useUISettings` (localStorage + backend `user.ui_settings` two-way sync). Add a key to `UI_SETTINGS_KEYS`.
2. **Bookmarkable session state** (active filters, search query, sort, current tab in detail views) → **URL query params**. Anyone copying the link reproduces what they see. **Active gallery filter must be in URL.**
3. **Ephemeral session state** (open dialog, hover, expansion) → `ref` if local, Pinia store if cross-component within the session.

Don't push state into `useUISettings` "so it persists", follow the rule above. Layer 3 never touches `localStorage`: if a value has to survive a reload, it is layer 1 or the per-entity variant below, not ephemeral state.

**Per-entity device preferences** (a bezel hidden for one game, the core picked for one game) are a narrow variant of layer 1: they persist per device but stay out of `useUISettings`, because they are keyed by entity rather than global and must not sync to `user.ui_settings`. Use `useLocalStorage` from VueUse with `writeDefaults: false` and a `serializer`, not a `ref` plus a `watch` plus `localStorage.setItem`. Key it off the route param so it binds before the entity resolves, and make the read fail safe to the default so a stale value can't wedge the view.

## D2. Async and reactive lifecycle

Three mistakes that keep reaching review:

1. **Snapshot before the first `await`.** Any reactive value a decision depends on can move while requests are in flight. Read it into a local before the call, not between calls: `const wasAllFavorited = allFavorited.value` goes above `await ensureFavoriteCollection()`, because the response replaces the very `rom_ids` that `allFavorited` derives from.
2. **Watch the narrowest source.** `watch(() => authStore.user, ...)` refires on every unrelated profile update, which then needs a manual "already ran for this id" flag. Watch a derived primitive instead so the watch is self-guarding: `() => user?.oauth_scopes.includes("tasks.run") ? user.id : null`.
3. **Guard late resolutions with `useIsAlive()`** (`src/v2/composables/useIsAlive/`), not a local `unmounted` flag plus `onBeforeUnmount`. It uses `onScopeDispose`, so it also works inside another composable. VueUse's `useMounted` is not a substitute.

Name a helper for what it touches: `syncCachedRom`, not `syncRom`, when it updates the cache and does not fetch.

## E. Pagination & infinite scroll

- `LoadMore` (`RBtn` + `RSpinner` + IntersectionObserver) is the canonical fallback when virtualization stalls.
- `RVirtualScroller` (`src/v2/lib/structural/`, wrapping `v-virtual-scroll`) is the substrate for large lists/grids.
- Page size lives in the store (`fetchLimit`); not user-configurable for now.
- **Scroll restoration** on back-nav: Vue Router `scrollBehavior` + Pinia in-session offset. URL holds filters/sort/search but **not** scroll offset.

## F. Forms & validation

- Use the **`RForm` primitive** (wraps `v-form`: Enter-to-submit when valid, scroll-to-first-error after a failed `validate()`). **Never use `v-form` directly.**
- **Native Vuetify rules** — no Zod/Yup. Rules are arrays of `(v) => true | string`.
- **Reusable rules** in `src/v2/utils/validation.ts` (`required(msg?)`, `email`, `asciiOnly`, `lengthBetween`, `usernameLength/Chars`, `passwordLength`). Utility code _may_ call `i18n.global.t(...)` (the no-i18n rule covers lib primitives, not utils).
- **Submit pattern:** `await formRef.value?.validate()` before the API call; submit button uses `:loading="submitting"`; errors → snackbar; field errors stay in-place via `:error-messages`.

## G. Permissions

- Action vocabulary `domain.action` (`rom.upload`, `rom.delete`, `library.scan`, `user.create`, `app.admin`) in `src/v2/composables/useCan/actions.ts`.
- Scope vocabulary:
  ```ts
  type PermissionScope =
    | { kind: "global" }
    | { kind: "platform"; id: number }
    | { kind: "collection"; id: number }
    | { kind: "rom"; id: number };
  ```
- **`useCan(action, scope?)`** returns `ComputedRef<boolean>`, reactive to `permissionsStore.grants`. Without scope: "can do this anywhere."
- `stores/permissions.ts` holds normalised grants, hydrated from `authStore.user.role` via the role-map (`installPermissionsHydration()` in `AppLayout`); a future `/permissions/me` will replace it.
- **`v-if`** to hide options a user shouldn't see; **`:disabled`** with tooltip when the option must be visible but blocked.
- **Backend is source of truth** — frontend is a UX hint. Never bypass with inline `user.role === "..."`. All grants are pre-loaded (no `useCanAsync`).

## H. Destructive confirmations

Three friction levels:

- **Low / High** → shared composite `ConfirmDialog` (`components/shared/`) opened via `useConfirm({ title, body, confirmText, tone, requireTyped }) => Promise<boolean>` (mounted once in `GlobalDialogs`).
- **Medium** → a feature composite when the flow needs extra options (e.g. `DeleteRomDialog` with per-item filesystem checkboxes).

Common rules:

- All destruction goes through a dialog — no silent destructive action.
- Confirm button is danger-toned; **focus starts on Cancel**; Enter cancels.
- Success → success snackbar or navigate away, dialog closes. Error → error snackbar, dialog stays open. During action → confirm shows `:loading`, cancel disabled.
- The destructive control respects `useCan(action, scope)`.
- **No "don't ask again."** **Type-to-confirm (`requireTyped`) is required when the action affects the filesystem.**
