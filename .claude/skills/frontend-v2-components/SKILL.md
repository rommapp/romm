---
name: frontend-v2-components
description: Building or modifying components in the RomM v2 frontend (frontend/src/v2/). Use when creating/editing v2 primitives (R* components in src/v2/lib/), shared composites, or feature composites — covers the three-tier model, file/folder conventions, SFC structure, import order, barrels, Storybook requirements, and v2 anti-patterns. Trigger on any work under frontend/src/v2/.
---

# RomM Frontend v2 — Component Constitution

This governs work inside `frontend/src/v2/`. **v1 is frozen** (`src/views/`, `src/components/`, `src/console/`, `src/layouts/`) — never refactor it; it will be deleted wholesale in a final wave. v2 is gated by `user.ui_settings.uiVersion`.

> Official language for all code, comments, identifiers, `.md`, and commit/PR messages: **English**.

Related skills: `frontend-v2-theming` (tokens/colors), `frontend-v2-input` (focus/gamepad/responsive), `frontend-v2-patterns` (errors/loading/forms/permissions/confirmations), `frontend-i18n`, `pre-pr-verification`.

---

## Premises (stable)

1. **v1 is frozen.** Don't touch `src/views/`, `src/components/`, `src/console/`, `src/layouts/`. When coexistence forces a v2 fork of a store/composable/util, annotate the v1 export with `@deprecated` pointing at the v2 replacement.
2. **Three component tiers** (below).
3. **Shared resources are canonical.** Pinia stores, API services, OpenAPI types (`src/__generated__/`), locales, utils — v2 *imports* them, never forks them. Additive changes to shared resources are allowed; changing a shared store API to work around a v2 call-site issue is not.
4. **TypeScript strict.** Zero `any` (justify with a comment if unavoidable). No `as unknown as ...`; fix the source or define an intermediate type.
5. **Universal substitution.** When an `R*` primitive exists, use it. If it doesn't, create or extend it. Never drop to raw HTML or raw Vuetify when a primitive applies.
6. **Wrapper contract.** Wrappers around Vuetify use `defineOptions({ inheritAttrs: false })` + `v-bind="$attrs"` + slot passthrough, and accept every prop/slot of the wrapped component.
7. **Layout via Vuetify utility classes + our wrappers, not plain CSS.** Use `d-flex`, `pa-4`, `align-center` directly. Vuetify layout components (`v-row`, `v-col`, `v-container`, `v-spacer`, `v-app`, `v-main`) get wrapped as `R*` on first use (lazy).
8. **Accessibility & performance** are requirements: semantic HTML, focus management, contrast, ARIA on icon-only controls; lazy-load heavy views, virtualize large lists, stable `:key` on every `v-for`.

---

## The three tiers

| Tier                  | Path                           | Prefix         | Stores/services/router/emitter/i18n | Story     | Domain knowledge                  |
| --------------------- | ------------------------------ | -------------- | ----------------------------------- | --------- | --------------------------------- |
| **Primitive**         | `src/v2/lib/`                  | `R*` mandatory | **No**                              | Mandatory | None                              |
| **Shared composite**  | `src/v2/components/shared/`    | no prefix      | Yes                                 | Optional  | Cross-feature, no specific domain |
| **Feature composite** | `src/v2/components/<feature>/` | no prefix      | Yes                                 | Optional  | Feature-specific                  |

### A component is a primitive only if all three hold

1. Does not depend on stores, services, router, or emitter.
2. No knowledge of a product domain (ROM, Platform, Collection, User…). `RAvatar` yes, `UserAvatar` no.
3. Its API can be described without naming features — generic props/slots/events.

If any fails: **shared composite** if generic across features, **feature composite** if owned by one feature. Edge cases get raised to the user, not auto-decided. Consumer count never demotes a primitive.

### Primitive boundaries

- **Can use**: tokens, other primitives, Vue/Vuetify, generic composables (`useInput*`, `useFocus*`).
- **Cannot use**: Pinia stores, API services, `emitter`, `router` (a `RouterLink` may be accepted as a prop), `i18n` directly. **No `$t()` in primitives** — text comes via props or slots.

---

## File & folder conventions

- **Primitive**: one per folder — `RFoo/RFoo.vue`, `RFoo/RFoo.stories.ts`, `RFoo/index.ts`, optional `RFoo/types.ts`.
- **Composite**: flat `.vue` if one file suffices; a folder with the same internal structure (no story required) if it has sub-pieces.
- **Barrel**: `src/v2/lib/index.ts` re-exports every primitive — update it when a new primitive ships. Composites are imported directly by path; no barrel. No single-file `index.ts` that just re-exports to shorten a path.

### SFC structure

- `<script setup lang="ts">` always.
- `defineOptions({ inheritAttrs: false })` on every wrapper, paired with `v-bind="$attrs"` and slot passthrough (without the bind, attrs vanish silently).
- Props via `defineProps<Props>()` (interface), never runtime declarations. Emits via `defineEmits<{...}>()`. Slots with payload via `defineSlots<{}>()`.
- Order: `<script setup>` → `<template>` → `<style scoped>`. Unscoped `<style>` (teleport overrides only) goes after the scoped block.

### Import order & aliases

```ts
// 1. External
import { computed, ref } from "vue";
// 2. v2 primitives
import { RBtn, RDialog } from "@v2/lib";
// 3. v2 composables / shared
import { useCan } from "@/v2/composables/useCan";
// 4. v2 feature siblings
import GameCard from "@/v2/components/GameCard.vue";
// 5. Canonical shared resources
import storeAuth from "@/stores/auth";
import type { SimpleRom } from "@/__generated__";
```

- `@v2/lib` — primitives barrel. `@/v2/...` — anything else under v2. `@/...` — canonical shared resources. Never relative paths (`../../foo`) when an alias exists.
- Shared v2 types live in `src/v2/types/`; backend types come from `src/__generated__/`; not `src/types/` (legacy).

### Composables

- `use` prefix; single named export from `composables/useFoo/index.ts`; fully typed args/return; no side effects on module load (init on first call). Creating a v2-only composable when a v1 equivalent exists is allowed.

### Console logging

- `console.error` allowed for production-visible errors. `console.log`/`console.warn` must not ship. `console.debug` is dev-only — remove before PR.

---

## Storybook (mandatory for `/lib`)

- Every primitive ships at least one story with controls and at least one variant per theme.
- A new interactive primitive that warrants gamepad navigation ships a `play()` interaction.
- Modified primitive: existing story must still render and its interactions still pass.
- `npm run test` runs Vitest **and** every `/lib` story's `play()` via `composeStories`. Don't duplicate coverage between Vitest (pure logic) and Storybook `play()` (components).

---

## Anti-patterns (beyond what the premises already say)

1. Don't change shared store APIs to work around a v2 call-site issue. (Fix the call site; the Gallery lesson was calling `romsStore.reset()` from the view, not adding `_fetchSeq` to the store.)
2. Don't drop to inline role checks — always go through `useCan` (see `frontend-v2-patterns`).
3. Don't reinvent a surface — dialog/menu/popover/card all go through their primitive; special cases become a new prop, not a parallel surface.
4. Don't use `v-form` directly — use `RForm`.
5. Don't add backwards-compat shims inside v2: delete removed code; no `// removed`, no renamed-but-unused exports, no deprecated wrappers that just call the new function.
6. Don't write redundant tests; don't touch v1; never `--no-verify` on commits.

**Allowed (often misread):** modifying shared stores/services/utils *additively*; creating v2-only composables; importing from `src/__generated__/`.

---

## Known debt (focused follow-ups)

- **Virtualisation migration** — `RVirtualScroller` (`src/v2/lib/structural/`) needs to absorb `GameGrid`/`LetterGroupedGrid` (structural refactor of `Platform.vue`/`Search.vue`/`Collection.vue`); `useLetterGroups` must become index-based for AlphaStrip scroll-spy.
- **`useGalleryFilterUrl`** — sync `galleryFilter` store fields to URL query params for bookmarkable links; mark v1 store usage `@deprecated`.
- **Vue Router scroll restoration** — galleries scroll custom containers (`.r-v2-plat__scroll`), not window; add a Pinia `routeFullPath → offsetTop` map with per-view hooks. Bundle with the virtualisation migration.
- **`useSocketEvent` composable** — typed socket subscriptions with mount/unmount cleanup (consumers currently wire `socket.on/off` by hand).
- **When v1 dies**: move `uiVersion` into `UI_SETTINGS_KEYS`; drop `.r-v2-*` scope classes (tokens move to `:root`); simplify `useUISettings` sync; delete `useGameAnimation`; drop the color-string→tone collapser in `NotificationHost`; remove the Vuetify rule arrays in `stores/users.ts`.

Full reference: `docs/FRONTEND_ARCHITECTURE.md`.
