# RomM Frontend v2 — Full UI Overhaul Plan

## Context

RomM ships a Vue 3 + Vuetify SPA with ~216 components, 36 routes, 18 Pinia stores, 17 API services, and a completely separate **console mode** (`/console/*`) for TV/gamepad use. An artist is producing a new visual direction and we want to rebuild the UI on top of a custom component library (R-components wrapping Vuetify) with Storybook as the design-system workbench.

### Goals

1. Build a new UI **inside the existing `frontend/` directory**, living beside the current code in its own `src/v2/` subtree. Single bundle, single deploy.
2. **One user setting toggles between the old and new UI on the fly** — no reload needed, no backend route changes, no Docker/Nginx/proxy changes.
3. **Merge console mode into the normal UI** — the new UI is universally navigable by mouse, keyboard, touch, and gamepad. No more `/console/*` split.
4. Wrap Vuetify with a RomM design system (`src/v2/lib/`); artist reviews every component in Storybook before it lands in a view.
5. Ship in view-by-view waves so work is incremental and always demoable.

### Non-goals

- **No backend changes.** No new endpoints, no FastAPI catch-all, no model migration (`user.ui_settings` is already free-form JSON).
- **No Docker, Nginx, proxy, or deploy config changes.** One bundle, one entry point, same serving path.
- No rewrite of stores, API services, OpenAPI codegen, sockets, or utils.
- The old UI (`src/views/`, `src/components/`, `src/layouts/`, `src/console/`) is **frozen** — we don't refactor it; we only delete it later once v2 is the default.

## Constraints & Key Decisions (Locked)

| Decision          | Choice                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Foundation        | Vuetify 3.9+ wrapped by R-components (forms, data-table, virtual scroll, etc. kept battle-tested)                              |
| Scope             | UI layer only — views, components, styling, theming, universal input                                                           |
| Location          | Inside `frontend/src/v2/`. One Vite config, one `package.json`, one `dist/`.                                                   |
| Switch            | `user.ui_settings.uiVersion: "v1" \| "v2"` — read in root component, swaps the app tree reactively. No reload required.        |
| Console vs normal | **Merged.** Universal gamepad/keyboard input in the new UI, no `/console/*` in v2                                              |
| Storybook         | Installed in `frontend/`, configured to only pick up `src/v2/**/*.stories.ts`. Artist reviews in Storybook before integration. |
| Shared state      | v2 imports existing Pinia stores, API services, locales, utils directly (no duplication)                                       |

## Directory Layout (inside existing `frontend/`)

```text
frontend/
├── .storybook/                  ← NEW — Storybook config (picks up only v2 stories)
│   ├── main.ts
│   ├── preview.ts
│   └── decorators/
│
├── src/
│   ├── main.ts                  ← unchanged plugin setup (Vuetify, Pinia, i18n, router)
│   ├── RomM.vue                 ← MODIFIED — gates on user.ui_settings.uiVersion
│   │
│   ├── plugins/                 ← shared by both UIs
│   │   └── router.ts            ← MODIFIED — conditionally loads v1 or v2 routes at runtime
│   │
│   ├── stores/                  ← unchanged, shared
│   ├── services/                ← unchanged, shared
│   ├── composables/             ← unchanged, v2 adds its own under src/v2/composables/
│   ├── locales/                 ← unchanged, shared
│   ├── utils/                   ← unchanged, shared
│   ├── __generated__/           ← unchanged, shared
│   ├── types/                   ← unchanged, shared
│   │
│   ├── layouts/                 ← OLD, frozen (Auth.vue, Main.vue)
│   ├── views/                   ← OLD, frozen
│   ├── components/              ← OLD, frozen
│   ├── console/                 ← OLD, frozen (its input system gets PORTED into v2)
│   ├── styles/                  ← OLD globals kept; v2 has its own tokens/global sheet
│   │
│   └── v2/                      ← NEW — all new UI lives here
│       ├── RomMV2.vue           ← v2 root (what RomM.vue mounts when uiVersion === "v2")
│       ├── lib/                 ← custom component library (R-components)
│       │   ├── index.ts         ← barrel export
│       │   ├── RBtn/
│       │   │   ├── index.ts
│       │   │   ├── RBtn.vue
│       │   │   └── RBtn.stories.ts
│       │   ├── RCard/
│       │   └── ... (~55 components)
│       ├── tokens/              ← design tokens as TS constants
│       ├── styles/
│       │   ├── tokens.css       ← :root CSS custom properties
│       │   └── global.css
│       ├── theme/               ← Vuetify theme derived from tokens
│       ├── layouts/             ← AuthLayout.vue, AppLayout.vue
│       ├── views/               ← route components
│       ├── components/          ← view-specific composites (not library-grade)
│       ├── composables/
│       │   ├── useInput/        ← UNIVERSAL input: keyboard + mouse + touch + gamepad
│       │   ├── useSpatialNav/   ← ported + generalized from src/console/composables/
│       │   ├── useFocusRing/    ← visible focus when navigating via keys/pad
│       │   └── useInputModality/← tracks last input device (mouse/touch/key/pad)
│       └── router/
│           └── routes.ts        ← v2 route table (no /console/*)
│
├── vite.config.js               ← MODIFIED — add path alias @v2, include v2 stories in build
├── package.json                 ← MODIFIED — add Storybook deps + scripts
└── tsconfig.json                ← MODIFIED — add @v2 path alias
```

## The Switch Mechanism (Pure Frontend, On-the-Fly)

**Single entry, dual app trees. No reload, no backend changes.**

1. `user.ui_settings.uiVersion` — new key, defaults to `"v1"`. Added to the existing `useUISettings` composable's typed schema.
2. **`frontend/src/RomM.vue`** becomes a thin gate:

   ```vue
   <script setup lang="ts">
   import { computed } from "vue";
   import { useUISettings } from "@/composables/useUISettings";
   import RomMV1 from "@/layouts/Main.vue";
   // existing app root (or current RomM.vue contents)
   import RomMV2 from "@/v2/RomMV2.vue";

   const { uiVersion } = useUISettings();
   const activeApp = computed(() =>
     uiVersion.value === "v2" ? RomMV2 : RomMV1,
   );
   </script>
   <template><component :is="activeApp" /></template>
   ```

3. The router is shared but **routes resolve through the active app tree**. Easiest model: v2's `RomMV2.vue` contains its own `<router-view>` with its own layout chain, and routes use `meta.uiVersion` to restrict to v1 or v2. A router guard redirects to a compatible route if the user flips while on an incompatible one.
4. The settings toggle writes `uiVersion`, the reactive `activeApp` recomputes, and the alternate tree mounts instantly. The stores, router, and i18n instance all survive the swap (same plugin instances).

**Pros:** zero backend work, zero build split, one bundle, instant switch.
**Tradeoff:** both old and new component trees ship in the same bundle until v1 is removed. That's fine — this is temporary.

**Critical files:**

- `frontend/src/RomM.vue` — turn into the gate
- `frontend/src/composables/useUISettings.ts` — add `uiVersion` key
- `frontend/src/plugins/router.ts` — add `meta.uiVersion` handling + fallback guard
- `frontend/src/v2/RomMV2.vue` — new v2 root
- A small toggle in **both** Settings → UserInterface (v1 and v2) so users can flip back

## Universal Input System (Merging Console + Normal)

The existing `src/console/input/` (bus, actions, keyboard, gamepad) + `src/console/composables/` (useSpatialNav, useInputScope, useRovingDom, useElementRegistry) are the right primitives — they're just locked to `/console/*`. In v2 we **port and generalize them for the whole UI**.

**Plan:**

1. Port input bus, keyboard listener, and gamepad poller into `frontend/src/v2/composables/useInput/`. Same stack-based scope manager, same 12 actions.
2. **Activated globally** in `v2/layouts/AppLayout.vue`. Keyboard + gamepad listeners always on; actions dispatch to the focused scope.
3. **Input modality tracking** (`useInputModality`) sets `data-input="mouse|touch|key|pad"` on `<html>`. CSS reads that attribute to scale focus rings, enlarge hit targets, show/hide D-pad hints.
4. **Every R-component is focusable and focus-ring-styled.** Cards, list items, tabs, menu items, buttons all participate in spatial nav.
5. **Focus grid primitives** — `RFocusZone`, `RFocusGrid`, `RFocusRow`, `RFocusColumn` — views declare their focus layout via these wrappers.
6. **SFX (procedural Web Audio)** kept, off by default for mouse users, auto-enabled when modality=pad.
7. **No `/console/*` routes in v2.** That whole tree disappears.

## Design Tokens & Theming

**Source of truth:** `frontend/src/v2/tokens/index.ts` (TypeScript) mirrored to `frontend/src/v2/styles/tokens.css` (CSS custom properties). The Vuetify theme (`v2/theme/vuetify.ts`) derives its palette from the same tokens so `$vuetify.theme.colors.primary === var(--r-color-brand-primary)`.

| Category       | Examples                                                                                                                                  |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Color brand    | `--r-color-brand-primary`, `--r-color-brand-accent`, `--r-color-romm-red/green/blue/gold`                                                 |
| Color semantic | `--r-color-bg`, `--r-color-bg-elevated`, `--r-color-surface`, `--r-color-fg`, `--r-color-fg-muted`, `--r-color-border`, `--r-color-focus` |
| Color status   | `--r-color-success/warning/danger/info`                                                                                                   |
| Typography     | `--r-font-family-sans/display`, `--r-font-size-xs…3xl`, `--r-line-height-*`, `--r-font-weight-*`                                          |
| Spacing        | 4px base: `--r-space-0…12`                                                                                                                |
| Radius         | `--r-radius-sm/md/lg/xl/full`                                                                                                             |
| Elevation      | `--r-elev-1…5`                                                                                                                            |
| Motion         | `--r-motion-fast/med/slow`, easing curves                                                                                                 |
| Focus          | `--r-focus-ring-width/color/offset` — differs per modality (mouse vs pad)                                                                 |

**Dark/light at launch.** Artist provides both palettes. Additional variants deferred.

**v1 tokens untouched.** The existing `src/styles/themes.ts` and Vuetify dark/light themes stay — v2's Vuetify theme lives separately and is registered under the theme names `v2-dark` and `v2-light`. When v2 mounts, it calls `theme.global.name.value = "v2-dark"` (or "v2-light" per user setting). Switching back to v1 restores `"dark"`/`"light"`.

## Storybook Baseline

**Installed inside `frontend/`** (no separate directory, no separate package.json).

- **Framework:** `@storybook/vue3-vite` 10.x
- **Addons:** `@storybook/addon-docs`, `@storybook/addon-a11y`, `@storybook/addon-themes`, `@chromatic-com/storybook`, `@storybook/addon-vitest`
- **Story glob:** `src/v2/**/*.stories.ts` — explicitly excludes v1 code
- **Decorators:**
  - Vuetify decorator wraps stories in `<v-app>` with the v2 theme
  - Pinia decorator — fresh store per story, optional seeded state
  - i18n decorator — locale picker in toolbar, default `en_US`
  - Router mock decorator
- **Global preview:** imports v2 `tokens.css` + `global.css` + fonts; theme switcher toolbar toggles `v2-dark`/`v2-light`.
- **Interaction tests:** every interactive R-component ships at least one `play()` covering click, keyboard, and simulated gamepad key events.

**Scripts added to `frontend/package.json`:**

- `storybook` — dev server
- `storybook:build` — static build
- `storybook:test` — interaction test runner

## Component Library (`frontend/src/v2/lib/`)

**Per-component convention:**

```text
RComponentName/
├── index.ts              ← export
├── RComponentName.vue    ← wraps Vuetify, defineOptions({ inheritAttrs: false })
├── RComponentName.stories.ts
└── types.ts              ← prop types (if non-trivial)
```

**Stay raw (no wrapper):** layout (`v-row`, `v-col`, `v-app`, `v-main`, `v-container`, `v-spacer`), composables (`useDisplay`, `useTheme`), complex composites (`v-data-table`, `v-navigation-drawer`, `v-expansion-panels`, `v-autocomplete`, `v-combobox`, `v-form`), transitions.

### Catalog (derived from every view in `docs/FRONTEND_ARCHITECTURE.md`)

**Wave 0 — Leaves**
`RBtn`, `RIconBtn`, `RIcon`, `RDivider`, `RChip`, `RAvatar`, `RImg`, `RBadge`, `RProgressCircular`, `RProgressLinear`, `RAlert`, `RKbd`, `RSpinner`, `RSkeletonBlock`

**Wave 1 — Form inputs**
`RTextField`, `RTextarea`, `RCheckbox`, `RSwitch`, `RFileInput`, `RSelect`, `RRadioGroup`, `RSlider`, `RRating`, `RColorPicker`, `RSearchInput`

**Wave 2 — Structural**
`RCard`, `RCardHeader`, `RCardBody`, `RCardFooter`, `RSection`, `RSheet`, `RToolbar`, `RAppBar`, `RTabs`, `RTab`, `RTabPanel`, `RList`, `RListItem`, `RBtnGroup`, `RMenu`, `RTooltip`, `RPopover`, `RSnackbar`, `RBanner`

**Wave 3 — Overlays**
`RDialog`, `RDrawer`, `RBottomSheet`, `RConfirmDialog`, `RLightbox`

**Wave 4 — Media**
`RCover` (smart cover w/ fallback + procedural SVG via existing `utils/covers.ts`)
`RPlatformIcon`, `RHeroImage`, `RCarousel`, `RCarouselItem`, `RPDFViewer`, `RVideoHoverPreview`

**Wave 5 — Data display**
`RDataTable`, `RVirtualList`, `RVirtualGrid`, `RStat`, `RStatGroup`, `RKeyValue`, `RMetadataGrid`, `RBreadcrumbs`, `RPagination`, `RLoadMore`

**Wave 6 — Universal-nav primitives (new)**
`RFocusZone`, `RFocusGrid`, `RFocusRow`, `RFocusColumn`, `RInputHint`, `RAlphaJump`

**Wave 7 — Feedback & state**
`RNotification`, `RNotificationHost`, `RProgressBanner`, `RErrorState`, `RLoadingState`, `REmptyState` (variants for game/platform/collection/saves/firmware/search)

Total: **~55 library components.** All ship with stories.

## View Migration Waves

Each wave = one reviewable PR (or small PR stack). Order chosen so each wave is demoable end-to-end with the UI toggle.

| #   | Wave                          | Views / Artifacts                                                                                                                                                                                                 | Depends on                                 |
| --- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| 0   | **Scaffold**                  | `src/v2/` skeleton, `RomMV2.vue`, tokens, global styles, `uiVersion` setting + toggle in Settings → UI, Storybook baseline, `@v2` alias                                                                           | —                                          |
| 1   | **Auth flows**                | `/login`, `/reset-password`, `/register`, `/setup` + `AuthLayout`                                                                                                                                                 | Wave 0, leaves + form inputs               |
| 2   | **App shell + Home**          | `AppLayout`, top bar, drawers, `/` home dashboard (stats, carousels, platforms, collections)                                                                                                                      | Wave 1, structural + media + universal-nav |
| 3   | **Gallery**                   | `/platform/:p`, `/collection/:c`, `/collection/virtual/:c`, `/collection/smart/:c`, `/search` — grid + table, filters, infinite scroll, multi-select                                                              | Wave 2, data display                       |
| 4   | **Game details**              | `/rom/:r` — 8 tabs, PDF viewer, screenshots lightbox, action bar, save/state tabs                                                                                                                                 | Wave 3, overlays                           |
| 5   | **Players**                   | `/rom/:r/ejs`, `/rom/:r/ruffle` — emulator shells, BIOS/core/save pickers. Gamepad flows through naturally                                                                                                        | Wave 4                                     |
| 6   | **Scan + Patcher + Pair**     | `/scan` (socket.io log), `/patcher` (dropzones, worker), `/pair` (code display)                                                                                                                                   | Wave 3                                     |
| 7   | **Settings suite**            | `/user/:u`, `/user-interface`, `/library-management`, `/metadata-sources`, `/client-api-tokens`, `/administration`, `/server-stats`                                                                               | Wave 3                                     |
| 8   | **Global dialogs**            | 15+ dialogs (EditRom, MatchRom, DeleteRom, UploadRom, NoteDialog, ShowQRCode, Saves/States upload/delete/select, AddRoms/RemoveRoms, RefreshMetadata, SearchCover, LoadingDialog)                                 | Waves 3-4                                  |
| 9   | **Gamepad polish pass**       | Traverse every v2 view with a controller; fix focus orders, input hints, SFX, scroll-into-view                                                                                                                    | All previous                               |
| 10  | **Default flip + v1 removal** | Change `uiVersion` default to `"v2"` in `useUISettings`; users who never customized get v2. Delete `src/layouts/{Auth,Main}.vue`, `src/views/`, `src/components/`, `src/console/`. Promote `src/v2/*` to `src/*`. | All previous                               |

**Per-wave acceptance:**

- R-components used exist in `src/v2/lib/` with stories + interaction test.
- View renders in Storybook (view-level story) AND in-app with `uiVersion="v2"`.
- Navigable via mouse, keyboard, touch, gamepad (from Wave 2 onward).
- `npm run typecheck`, `npm run lint`, `npm run storybook:test` all green.
- Artist sign-off on the view in Storybook preview.
- Toggling `uiVersion` back to `"v1"` still works without reload.

## Shared Resources (Reused by v2, Untouched)

| Resource                                       | v2 usage                                                                                                                                                             |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pinia stores (`src/stores/*`)                  | Direct import. No duplication, no fork.                                                                                                                              |
| API services (`src/services/api/*`)            | Direct import.                                                                                                                                                       |
| Socket.IO client (`src/services/socket.ts`)    | Direct import.                                                                                                                                                       |
| OpenAPI generated types (`src/__generated__/`) | Direct import.                                                                                                                                                       |
| Locales (`src/locales/*`)                      | Direct import; new keys added here and consumed by both UIs.                                                                                                         |
| Utils (`src/utils/*`)                          | Direct import. Procedural covers wrapped by `RCover`.                                                                                                                |
| Existing composables                           | v2 imports `useUISettings`, `useFavoriteToggle`, `useGameAnimation` as-is. New ones (`useInput`, `useSpatialNav`, `useInputModality`) live in `src/v2/composables/`. |

## Critical Files (New)

- `frontend/.storybook/main.ts`, `preview.ts`
- `frontend/src/v2/RomMV2.vue` — v2 root (own `<router-view>`)
- `frontend/src/v2/tokens/index.ts` + `frontend/src/v2/styles/tokens.css`
- `frontend/src/v2/theme/vuetify.ts` — registers `v2-dark`/`v2-light` themes
- `frontend/src/v2/composables/useInput/{bus,keyboard,gamepad,actions,scope}.ts` (ported from `src/console/input/`)
- `frontend/src/v2/composables/useSpatialNav.ts` (ported from `src/console/composables/`)
- `frontend/src/v2/composables/useInputModality.ts` (new)
- `frontend/src/v2/layouts/{AuthLayout,AppLayout}.vue`
- `frontend/src/v2/router/routes.ts` + integration into existing `src/plugins/router.ts` via `meta.uiVersion`

## Critical Files (Modified, Existing)

- `frontend/src/RomM.vue` — turn into the gate (swaps between v1 root and `RomMV2`)
- `frontend/src/composables/useUISettings.ts` — add `uiVersion: "v1" | "v2"` (defaults to `"v1"` until Wave 10)
- `frontend/src/plugins/router.ts` — add `meta.uiVersion` support + guard that redirects incompatible routes when `uiVersion` changes
- `frontend/src/views/Settings/UserInterface.vue` (v1) — add a switch to flip `uiVersion` (so users can opt in from the old UI)
- `frontend/src/v2/views/Settings/UserInterface.vue` (v2) — mirror the switch (so users can go back)
- `frontend/vite.config.js` — add `@v2 → ./src/v2` alias, ensure Storybook deps coexist
- `frontend/package.json` — Storybook deps + scripts
- `frontend/tsconfig.json` — add `@v2/*` path alias

## Out of Scope (Explicitly Untouched)

- Backend — no new endpoints, no model migrations (`ui_settings` already a free-form JSON column, just add a key)
- Docker, Dockerfile, entrypoint scripts
- Nginx config, proxy config
- Deploy/serving path — same single bundle from the same `dist/`
- Stores, API services, OpenAPI codegen, sockets, utils
- v1 UI code — frozen, deleted wholesale in Wave 10 (not refactored)

## Verification

**Per-wave checks:**

1. `cd frontend && npm run typecheck` → 0 errors
2. `cd frontend && npm run storybook` → every R-component in the wave renders, themes toggle, a11y panel clean
3. `cd frontend && npm run storybook:test` → interaction tests pass
4. `cd frontend && npm run dev` → default loads as v1 (unchanged). Flip toggle in Settings → instantly re-mounts as v2 with the wave's views functional. Flip back → v1.
5. Full smoke test of the wave's views in both themes.

**Cross-cutting smoke tests (Wave ≥ 2):**

- Mouse-only: login → platform → ROM → play
- Keyboard-only (Tab, arrows, Enter): same path
- Gamepad-only (D-pad + A/B): same path
- i18n: switch to `ja_JP` — no layout breakage
- Theme swap in real time

**Wave 10 (flip & remove):**

- All 36 original routes have v2 equivalents (or are explicitly retired — `/console/*` is gone; `/april-fools` decision TBD)
- Flip `uiVersion` default to `"v2"`
- Delete v1 files wholesale in a follow-up PR; promote `src/v2/*` to `src/*`
- Remove `@v2` alias; Storybook glob becomes `src/**/*.stories.ts`

## Open Questions to Resolve During Execution

- Should the v2 AppLayout share the drawer/app-bar concept with v1, or go fully custom? (Artist input.)
- Should `/april-fools` survive the rebuild?
- Router `meta.uiVersion` guard behavior when a user flips mid-session on a route that only exists in one UI — redirect to `/` or the closest equivalent? (Decide in Wave 0.)
- Procedural SFX volume/enablement default per modality — confirm in Wave 9.
- Do we keep the PWA manifest/service worker untouched or refresh the icons/theme color? (Decide in Wave 0.)
