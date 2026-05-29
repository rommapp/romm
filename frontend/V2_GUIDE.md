# RomM Frontend v2 — Working Guide

Companion to [`V2_PLAN.md`](./V2_PLAN.md). This file is the living reference for the v2 rebuild: what's built, what's not, and the rules we've agreed to follow.

The plan (`V2_PLAN.md`) is the _intent_; this doc is the _state_ + _playbook_.

---

## 1. Directives — non-negotiable working rules

These came from direct user instructions during the build. Any future session (human or AI) working on v2 must follow them unless the user changes the call.

### 1.1 Build the custom library as we go

> Every reusable visual piece belongs in `frontend/src/v2/lib/` as an `R*` component. Do **not** write raw HTML/CSS for anything that might recur — even once. If a pattern shows up in a single view and we suspect another view will want it, extract it now.

- **Vuetify first, always.** Before writing any SVG, CSS, or markup, check whether Vuetify already ships the thing. If it does, wrap it as an `R*` component — do not reinvent. `v-icon` covers icons (MDI webfont, 7k+ glyphs), `v-menu` covers dropdowns, `v-text-field` covers inputs, etc. Inline `<svg>` blocks in production v2 code are a smell — replace them with `<RIcon icon="mdi-…" />`.
- **Patterns → components, even the first time you notice.** If you're writing the same visual/markup twice (same three-button row, same meta-info strip, same labeled chip grid), extract immediately. Don't wait for the third occurrence; the review cost of one extra file is lower than the review cost of diverging copies. The whole GameActions / InfoGrid / MetadataProviderChips extraction came from noticing patterns — do the same.
- Wrap Vuetify components (`v-btn`, `v-menu`, `v-text-field`, …) with thin `R*` wrappers that apply RomM defaults + visual tokens.
- Purely presentational surfaces (menu panels, tiles, mosaics, pills, alpha strips) are first-class library components too — they don't have to wrap Vuetify; they just have to live in `src/v2/lib/`.
- **Never** inline styling or markup for a visual that belongs to the design system. If you catch yourself doing it mid-task, stop and extract before moving on.
- Views compose R-components. Views should be mostly: fetch data → render R-components → wire events.

Practical checklist when building something new:

- [ ] Does Vuetify already ship this? → Wrap it. Don't re-implement.
- [ ] Is the thing I want an icon? → `<RIcon icon="mdi-…" />` or the `icon` prop on `RIconBtn`/`RBtn`/`RMenuItem`. Never inline `<svg>`.
- [ ] Does the visual only make sense inside one view? OK to inline.
- [ ] Does it look like a "card", "tile", "panel", "row", "strip", "chip", "button", "menu", "field", "badge"? → R-component.
- [ ] Am I writing the same markup or CSS block a second time? → Extract now, not later.
- [ ] Did I just re-implement a Vuetify primitive? → Wrap the Vuetify one with an R-component.

### 1.2 Pure frontend scope

- No backend changes, no Docker changes, no Nginx changes, no proxy config changes.
- Stores / API services / locales / utils from `frontend/src/*` are imported directly — no duplication, no fork.
- Shared v1 components CAN be re-used from v2 temporarily when the logic is heavy (v1 `PDFViewer`, `SoundtrackPlayer`, `EditRomDialog`, etc.). Mark them for future v2-native replacement in the inventory below.

### 1.3 On-the-fly v1 ↔ v2 toggle

- `user.ui_settings.uiVersion` ∈ `{ "v1", "v2" }` — stored via a module-level singleton ref (`composables/useUiVersion.ts`) so a write from any component propagates reactively without a reload.
- Named Vuetify views (`components: { default: v1Comp, v2: v2Comp }`) make the two trees coexist under the same URLs.
- `RomM.vue` is the gate; it picks which `<router-view>` name to render.

### 1.4 Palette

- Primary = v1 purple `#8B74E8` (dark) / `#371F69` (light). The mockup's red is kept only as `--r-color-romm-red` for chip/icon accents.
- Accent = v1 peach `#E1A38D`. Mockup's `#A78BFA` purple isn't in use.
- Fav heart = `#ff4f6b` (`--r-color-fav`), independent of primary.
- See `src/v2/tokens/index.ts` + `src/v2/styles/tokens.css` for the full system.

### 1.5 Mockup as the visual reference

- Artist's mockup lives at [https://mockup.thebirdcage.tv](https://mockup.thebirdcage.tv) (single-page Vue SPA; routes share one HTML file).
- Design language: near-black base, translucent glass surfaces, blurred cover art backdrop, Segoe UI / system stack, 4px rhythm, dense 10–13 px typography, pill-shape buttons / chips, `8px` card art radius.
- Don't chase pixel-perfect — match the language (spacing, weights, blur, shadows, alpha tiers) and keep structural code clean.

---

## 2. Directory map

```text
frontend/
├── V2_PLAN.md                    # original plan (intent)
├── V2_GUIDE.md                   # THIS file (state + rules)
│
├── .storybook/                   # Storybook config (v2 stories only)
│   ├── main.ts
│   └── preview.ts
│
└── src/
    ├── main.ts                   # also imports v2/styles/global.css
    ├── RomM.vue                  # gate: renders v1 or v2 tree via named router-view
    │
    ├── composables/
    │   └── useUiVersion.ts       # singleton ref for the v1/v2 toggle
    │
    ├── plugins/
    │   ├── router.ts             # every / child route uses components: { default, v2 }
    │   └── vuetify.ts            # registers v2-dark / v2-light themes alongside v1
    │
    └── v2/                       # ── EVERYTHING V2 LIVES HERE ──
        ├── RomMV2.vue            # (legacy shell wrapper — may be unused after layout refactor)
        │
        ├── tokens/index.ts       # design tokens in TS
        ├── styles/
        │   ├── tokens.css        # CSS-var mirror of tokens (scoped under .r-v2)
        │   └── global.css        # global utilities + backdrop layers
        │
        ├── theme/vuetify.ts      # v2-dark / v2-light Vuetify theme definitions
        │
        ├── router/routes.ts      # registry mapping route names → v2 lazy components
        │
        ├── layouts/
        │   ├── AppLayout.vue     # nav pill + background art + dialog mounts + user menu
        │   └── AuthLayout.vue    # centered card on the auth background
        │
        ├── views/
        │   ├── Home.vue          # dashboard of horizontal card rows
        │   ├── PlatformsIndex.vue
        │   ├── CollectionsIndex.vue
        │   ├── GameDetails.vue   # full-viewport blurred-cover layout
        │   ├── NotReady.vue      # fallback for routes without a v2 implementation
        │   ├── Auth/             # Login / Register / ResetPassword
        │   └── Gallery/          # Platform / Collection / Search
        │
        ├── components/           # VIEW-specific composites (not lib-grade)
        │   ├── GameActions/      # per-ROM action surface (list, MoreMenu, action row)
        │   └── GameDetails/
        │       ├── MediaTab.vue
        │       └── SoundtrackPanel.vue
        │
        ├── composables/
        │   ├── useBackgroundArt/ # inject/provide setter for the backdrop art
        │   └── useInputModality/ # tracks mouse/touch/key/pad for focus-ring scaling
        │
        └── lib/                  # ── THE CUSTOM COMPONENT LIBRARY ──
            ├── index.ts          # barrel — every R-component exported here
            ├── tokens/           # (kept empty; see v2/tokens/ above)
            └── R*/               # one folder per component (see inventory §4)
                ├── R*.vue
                ├── index.ts
                └── R*.stories.ts
```

---

## 3. R-component authoring template

Every R-component follows this skeleton. Copy it when starting a new one.

```text
src/v2/lib/RFoo/
├── index.ts          // export { default as RFoo } from "./RFoo.vue";
├── RFoo.vue
└── RFoo.stories.ts   // at least one story; more if variants matter
```

`RFoo.vue` body:

```vue
<script setup lang="ts">
// Short doc: what it wraps, when to use it, non-obvious defaults.
import { VFoo } from "vuetify/components/VFoo"; // if wrapping Vuetify

defineOptions({ inheritAttrs: false });

interface Props { /* typed props with sane defaults */ }
withDefaults(defineProps<Props>(), { /* … */ });

defineEmits<{ /* if needed */ }>();
</script>

<template>
  <VFoo v-bind="$attrs" class="r-foo" /* mapped props */>
    <template v-for="(_, slot) in $slots" #[slot]="slotProps">
      <slot :name="slot" v-bind="slotProps || {}" />
    </template>
  </VFoo>
</template>

<style scoped>
.r-foo { /* pull from --r-color-*, --r-space-*, --r-radius-* etc. */ }
</style>
```

Then register in `src/v2/lib/index.ts` under the right wave section.

---

## 4. R-component inventory (current)

**Rule of thumb:** A component earns its place in `src/v2/lib/` only if **(a)** it's a design-system primitive (single role: button, icon, menu, avatar, card, chip…), **(b)** two or more features depend on it, and **(c)** it ships with a Storybook story. Specializations live under `src/v2/components/<feature>/` and are imported directly — not through the `@v2/lib` barrel.

Every lib primitive below has a story. Missing a story = not a primitive yet.

### Form + text

| Component    | Wraps          |
| ------------ | -------------- |
| `RCheckbox`  | `v-checkbox`   |
| `RSelect`    | `v-select`     |
| `RTextField` | `v-text-field` |

### Layout + surface

| Component   | Wraps         |
| ----------- | ------------- |
| `RAlert`    | `v-alert`     |
| `RCard`     | `v-card`      |
| `RDivider`  | `v-divider`   |
| `RList`     | `v-list`      |
| `RListItem` | `v-list-item` |
| `RToolbar`  | `v-toolbar`   |

### Buttons + interactive

| Component  | Wraps                                                                                                |
| ---------- | ---------------------------------------------------------------------------------------------------- |
| `RBtn`     | `v-btn` — the only button primitive. Pass `icon="mdi-…"` for icon-only. No `RIconBtn` or `RBackBtn`. |
| `RRating`  | `v-rating`                                                                                           |
| `RTooltip` | `v-tooltip`                                                                                          |

### Menus

| Component      | Wraps                                                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------------------------------- |
| `RMenu`        | `v-menu`                                                                                                              |
| `RMenuPanel`   | _(presentational panel shell)_                                                                                        |
| `RMenuHeader`  | _(presentational — avatar/thumb + title + subtitle)_                                                                  |
| `RMenuItem`    | _(presentational — button/router-link/anchor; accepts `icon="mdi-…"` + `variant: "default" \| "active" \| "danger"`)_ |
| `RMenuDivider` | _(presentational separator)_                                                                                          |

### Display atoms

| Component           | Wraps                                                            |
| ------------------- | ---------------------------------------------------------------- |
| `RAvatar`           | `v-avatar`                                                       |
| `RBadge`            | `v-badge`                                                        |
| `RChip`             | `v-chip`                                                         |
| `RIcon`             | `v-icon` — the only way to render an icon. Never inline `<svg>`. |
| `RImg`              | `v-img`                                                          |
| `RPlatformIcon`     | _(presentational — `.ico` with SVG fallback)_                    |
| `RProgressCircular` | `v-progress-circular`                                            |
| `RSkeletonBlock`    | _(presentational — shimmer block)_                               |
| `RSpinner`          | delegates to `RProgressCircular`                                 |

### Data

| Component | Wraps                                                                                                                                                                 |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RTable`  | `v-data-table-server` / `v-data-table-virtual` / `v-data-table` via `variant` prop. v2 glass visuals; keeps sort / select / row-click / pagination. Slot pass-through |

### Domain-specific primitive

| Component   | Wraps                                                                 |
| ----------- | --------------------------------------------------------------------- |
| `RGameCard` | _(portrait cover + hover overlay; every ROM-listing surface uses it)_ |

### Removed from lib (demoted or deleted)

These existed as `R*` at one point but don't meet the "primitive" bar. They're now either **feature components** (see §4b) or **deleted**:

| Ex-primitive        | Where it lives now                            | Why                                                                     |
| ------------------- | --------------------------------------------- | ----------------------------------------------------------------------- |
| `RBackBtn`          | `components/shared/BackBtn.vue`               | RBtn + icon covers it                                                   |
| `RIconBtn`          | **deleted**                                   | RBtn's `icon` prop covers it; variant styling is a per-callsite concern |
| `RCover`            | **deleted**                                   | zero callers                                                            |
| `REyebrow`          | `.r-eyebrow` utility in `global.css`          | it's one font/letter-spacing rule, not a component                      |
| `RStat`             | `components/shared/Stat.vue`                  | specialization                                                          |
| `RInfoPanel`        | `components/Gallery/InfoPanel.vue`            | gallery-specific composite                                              |
| `RAlphaStrip`       | `components/Gallery/AlphaStrip.vue`           | gallery-specific                                                        |
| `RLoadMore`         | `components/Gallery/LoadMore.vue`             | gallery-specific                                                        |
| `RGameGrid`         | `components/Gallery/GameGrid.vue`             | gallery-specific                                                        |
| `RCollectionMosaic` | `components/Collections/CollectionMosaic.vue` | collection-specific                                                     |
| `RCollectionTile`   | `components/Collections/CollectionTile.vue`   | collection-specific                                                     |
| `RPlatformTile`     | `components/Platforms/PlatformTile.vue`       | platform-specific                                                       |
| `RCardRow`          | `components/Home/CardRow.vue`                 | Home-specific                                                           |
| `RFileRow`          | `components/GameDetails/FileRow.vue`          | GameDetails-specific                                                    |

---

## 4b. View-level sub-components (not library-grade)

View-specific composites that aren't reusable across the app live under `src/v2/components/<feature>/`. They follow the same authoring conventions as R-components (script-setup, typed props/emits, scoped styles, `inheritAttrs: false` when appropriate) but **aren't** exported from `@v2/lib`.

Rule of thumb: if the same block appears in more than one feature area, promote it to a library R-component. Otherwise keep it here.

### `src/v2/components/AppShell/`

| File                | Purpose                                                                                         |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| `BackgroundArt.vue` | Two-layer cross-fading blurred-cover backdrop (consumes the `r-v2-set-background-art` provider) |
| `AppNav.vue`        | Top nav: logo · centred tab pill · "classic UI" button · user menu                              |
| `UserMenu.vue`      | Avatar pill dropdown (Profile / Interface / Log out); owns the logout flow                      |
| `GlobalDialogs.vue` | Stack of emitter-driven dialog + notification mount-points (v1 dialogs re-used)                 |

### `src/v2/components/Auth/`

| File             | Purpose                                                                                             |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| `LoginForm.vue`  | Username + password form (password uses `PasswordField`); owns the API call + snackbar              |
| `ResetForm.vue`  | Username-only forgot-password form                                                                  |
| `OIDCButton.vue` | OIDC button with provider dashboard-icon (falls back to `mdi-key`); exposes `login()` for autologin |

### `src/v2/components/shared/`

Cross-feature helpers that don't belong to any one feature but aren't general enough to be lib primitives.

| File                   | Purpose                                                                                                                                                                           |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BackBtn.vue`          | Pill-style "go back" button (topbars on Gallery + GameDetails). Renders a `router-link` if `to` set, else emits `@click` for things like `router.back()`                          |
| `Stat.vue`             | KPI column — big value + tiny uppercase label. Used by InfoPanel and anywhere a stat column is shown                                                                              |
| `VersionTag.vue`       | Renders `SYSTEM.VERSION` from heartbeat; `link` prop renders as an anchor to the GitHub release. AuthLayout uses the plain variant; About dialog (future) uses the linked variant |
| `LanguageSelector.vue` | Glass-pill RMenu dropdown bound to the language store; syncs vue-i18n + persists to ui-settings. Shared by AuthLayout and (future) v2 Settings                                    |
| `AuthCard.vue`         | Card frame used by every auth view — logo + translucent dark gradient + padded inner column. Content goes in the default slot                                                     |
| `PasswordField.vue`    | RTextField with the show/hide eye toggle baked in. Default `variant="underlined"` for auth; override for other contexts                                                           |
| `AuthBackLink.vue`     | Small right-aligned "← Back to login" link (Register + ResetPassword). `to` overrides the default `/login`                                                                        |
| `PageHeader.vue`       | Top-of-page `h1` + optional count. `count` prop for the plain dim span, `#count` slot for richer content (chips). Default slot sits at the end of the header                      |
| `EmptyState.vue`       | Centered empty / no-results block. `variant="plain"` (dim centered text — index views) or `variant="boxed"` (dashed-border panel with MDI icon — search results)                  |

### `src/v2/components/Gallery/`

| File                    | Purpose                                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `InfoPanel.vue`         | Hero strip at the top of Platform / Collection gallery pages. Slots for cover / eyebrow / title / tags / stats / actions |
| `AlphaStrip.vue`        | A-Z-# jump sidebar for letter-grouped grids (only shown when `groupBy === "letter" && layout === "grid"`)                |
| `GameGrid.vue`          | Responsive auto-fill grid of `RGameCard`s with skeleton placeholders on initial load                                     |
| `GameList.vue`          | Sortable list layout — wraps `RTable` with ROM columns (Title / Size / Added / Released / ⭐ / 🔠 / 🌎 / Actions)        |
| `LoadMore.vue`          | "Load N more" button + IntersectionObserver sentinel for auto-fetch on scroll                                            |
| `LetterGroupedGrid.vue` | Skeletons / empty / letter-grouped RGameCard grid / "Load N more" — used only in `grid + grouped` mode                   |
| `GalleryToolbar.vue`    | GroupBy + Layout segmented controls + kebab mirror. Renders inline (`header`) or floating top-right (`floating`)         |

### `src/v2/components/Home/`

| File          | Purpose                                                                                                                             |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `CardRow.vue` | Horizontal-scrolling section with icon/title/count header and gradient left/right arrow overlays. Used for every Home dashboard row |

### `src/v2/components/Platforms/`

| File               | Purpose                                                                                   |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `PlatformTile.vue` | Platform card (`variant="row"` 150px or `variant="grid"` auto-fit). Wraps `RPlatformIcon` |

### `src/v2/components/Collections/`

| File                   | Purpose                                                                                                                    |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `CollectionMosaic.vue` | 2×2 cover grid for collection artwork (0 / 1 / 2-4 cover variants)                                                         |
| `CollectionTile.vue`   | Collection card (Home row + /collections grid) with `CollectionMosaic` + name + count; `kind` overlays "Smart" / "Virtual" |

### `src/v2/components/GameActions/`

Reusable, ROM-level action surface. Single source of truth for all per-ROM actions — every MoreMenu (on RGameCard, in GameDetails header, …) renders `GameActionsList` so the action set never diverges. Right-click is intentionally left to the browser (Open in new tab etc.).

| File                  | Purpose                                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GameActions.vue`     | Five-button action row for the GameDetails header: Play · Download · Favorite · Share · More. Every button is an `<RBtn icon="mdi-…" />`                            |
| `GameActionsList.vue` | The shared list of `RMenuItem`s for a ROM (Play / Download / Favorite / Add to collection / QR / Match / Refresh / Edit / Delete). Emits `close` after each action. |
| `MoreMenu.vue`        | Thin wrapper around `RMenu + RMenuPanel + GameActionsList` — the "More" dropdown for the header. `#activator` slot takes the trigger button                         |

### `src/v2/components/GameDetails/`

| File                        | Purpose                                                                                                                                             |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CoverColumn.vue`           | Fixed-width left column with the ROM cover (or placeholder); top-aligned                                                                            |
| `GameHeader.vue`            | Right-column header — 5 rows: title / meta / provider chips / tags / `<GameActions>`. Presentation only — all per-ROM actions live in `GameActions` |
| `MetadataProviderChips.vue` | Compact row of linked metadata providers (IGDB / MobyGames / RA / HLTB / …); hidden for unlinked                                                    |
| `DetailsTabs.vue`           | Underlined tab nav; v-model synced to `?tab=` in the URL                                                                                            |
| `OverviewTab.vue`           | Summary paragraph + status badge + InfoGrid (genres/dev/franchise/collections) + HLTBStrip                                                          |
| `InfoGrid.vue`              | 2-column labelled-chip grid; used by Overview                                                                                                       |
| `HLTBStrip.vue`             | 4-column How-Long-To-Beat stats bar                                                                                                                 |
| `PersonalTab.vue`           | Read-only personal stats (status / rating / difficulty / completion / last-played)                                                                  |
| `NotesTab.vue`              | Per-ROM notes — list + add/edit/delete form. Edit only for own notes; public notes from others read-only                                            |
| `AchievementsTab.vue`       | RA summary (earned/total · points · progression · missable) + type/status filters + per-achievement rows                                            |
| `MediaTab.vue`              | Manual / Soundtrack / Screenshots subtabs (Screenshots is conditional on `merged_screenshots`)                                                      |
| `ScreenshotsTab.vue`        | Responsive 16:9 grid (rendered inside MediaTab's Screenshots subtab)                                                                                |
| `RelatedGamesGrid.vue`      | Labelled grid of `IGDBRelatedGame` tiles — rendered once per section in both Additional and Related tabs                                            |
| `FilesTab.vue`              | List of `FileRow` rows for file-level metadata                                                                                                      |
| `FileRow.vue`               | Stacked label + value; `mono` prop renders value as a monospace chip (hashes/paths)                                                                 |
| `SoundtrackPanel.vue`       | Soundtrack player internals — pre-existing                                                                                                          |

---

## 4c. v2 composables (non-visual shared logic)

| File                            | Purpose                                                                                                                                                                                |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `composables/useBackgroundArt/` | Inject `r-v2-set-background-art` — views call with a URL to cross-fade the app backdrop                                                                                                |
| `composables/useInputModality/` | Tracks last input device (mouse/touch/key/pad); stamps `<html data-input>`                                                                                                             |
| `composables/useLetterGroups/`  | Groups a flat ROM list into A–Z (+ `#`) buckets + scroll-spy sync for `AlphaStrip`                                                                                                     |
| `composables/useGameActions/`   | Shared per-ROM action handlers (play / download / favorite / share / match / refresh / edit / remove). Consumed by `GameActionsList`, `GameActions`, and right-click `GameContextMenu` |
| `composables/useThemeClass/`    | Returns reactive `"r-v2-dark" \| "r-v2-light"` derived from the active Vuetify theme. Every layout root calls it so theme-scoped CSS flips correctly                                   |
| `composables/useGalleryMode/`   | Global gallery-view prefs (localStorage): `groupBy` (`"letter" \| "none"`), `layout` (`"grid" \| "list"`), `toolbarPosition` (`"header" \| "floating"`)                                |

---

## 5. Views — migration status

| Route                    | v2 file                           | Status | Notes                                                                                                              |
| ------------------------ | --------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------ |
| `/`                      | `Home.vue`                        | ✅     | Mockup dashboard rows (Continue Playing, Recently Added, Favorites, Platforms, Collections)                        |
| `/login`                 | `Auth/Login.vue`                  | ✅     | Password + forgot-password toggle + OIDC                                                                           |
| `/reset-password`        | `Auth/ResetPassword.vue`          | ✅     | —                                                                                                                  |
| `/register`              | `Auth/Register.vue`               | ✅     | —                                                                                                                  |
| `/setup`                 | —                                 | 🛑     | Still v1 (Setup wizard — big)                                                                                      |
| `/platforms`             | `PlatformsIndex.vue`              | ✅     | V2-only route, V1 redirects to Home                                                                                |
| `/platform/:p`           | `Gallery/Platform.vue`            | ✅     | Info panel + alpha strip + letter groups                                                                           |
| `/collections`           | `CollectionsIndex.vue`            | ✅     | Regular + smart + virtual with "Smart"/"Virtual" badge                                                             |
| `/collection/:c`         | `Gallery/Collection.vue`          | ✅     | Mosaic cover + same body as Platform                                                                               |
| `/collection/virtual/:c` | `Gallery/Collection.vue`          | ✅     | Dispatches by route name                                                                                           |
| `/collection/smart/:c`   | `Gallery/Collection.vue`          | ✅     | —                                                                                                                  |
| `/search`                | `Gallery/Search.vue`              | ✅     | Debounced search into the shared roms store                                                                        |
| `/rom/:r`                | `GameDetails.vue`                 | ✅     | Full-viewport blurred cover layout, tabs: Overview / Personal / Media / Screenshots / Additional / Related / Files |
| `/rom/:r/ejs`            | `Player/EmulatorJS.vue`           | ✅     | v2 chrome wrapping the v1 `<Player>` component verbatim (EJS\_\* globals + loader fallback preserved)              |
| `/rom/:r/ruffle`         | `Player/Ruffle.vue`               | ✅     | v2 chrome wrapping the v1 Ruffle injection verbatim (script loader + `createPlayer` preserved)                     |
| `/scan`                  | `Scan.vue`                        | ✅     | Glass config panel + live scan log; reuses `ScanPlatform` v1 primitive inside v2 expansion panels                  |
| `/patcher`               | `Patcher.vue`                     | ✅     | Glass drop-zones + controls; rom-patcher-js + web-worker pipeline ported verbatim from v1                          |
| `/pair`                  | `Pair.vue` (via `PairDispatcher`) | ✅     | Standalone card inside `PairShell` (AuthLayout-equivalent); dispatcher picks v1/v2 from `uiVersion` setting        |
| `/user/:u`               | `Settings/UserProfile.vue`        | ✅     | Avatar upload + account form (v2-native), wraps v1 RetroAchievements section                                       |
| `/user-interface`        | `Settings/UserInterface.vue`      | ✅     | v2-native UIVersion / Language / Theme cards; v1 Interface (advanced home toggles) embedded for now                |
| `/library-management`    | `Settings/LibraryManagement.vue`  | ✅     | v2 tabs (mapping / excluded / missing) wrapping v1 sub-components; config-not-mounted/writable alerts preserved    |
| `/metadata-sources`      | `Settings/MetadataSources.vue`    | ✅     | v2-native provider tiles with live API-key + heartbeat status indicators                                           |
| `/client-api-tokens`     | `Settings/ClientApiTokens.vue`    | ✅     | v2 shell around v1 ClientTokensTable                                                                               |
| `/administration`        | `Settings/Administration.vue`     | ✅     | v2 shell around v1 UsersTable / TokensTable / Tasks (scope-gated as in v1)                                         |
| `/server-stats`          | `Settings/ServerStats.vue`        | ✅     | v2 shell around v1 SummaryStats + PlatformsStats                                                                   |
| `/console/*`             | —                                 | ❌     | Gone in v2 — universal input merges console + normal                                                               |

V1 components still consumed by v2 (temporary — flagged for replacement):

- `frontend/src/components/Details/PDFViewer.vue` (used by `v2/components/GameDetails/MediaTab.vue`)
- `frontend/src/components/common/SoundtrackMiniPlayer.vue` (rendered by `RomM.vue`)
- `frontend/src/components/common/VolumeControl.vue` (lazy-imported by `v2/components/GameDetails/SoundtrackPanel.vue`)
- `frontend/src/components/common/Notifications/{Notification,UploadProgress}.vue` (global toast hosts — shared with v1 on the same emitter; rebuild scheduled after Wave 8)
- `frontend/src/components/common/Game/Card/Base.vue` (reused inside v2 `EditRomDialog` + `MatchRomDialog` as the cover-preview primitive)
- `frontend/src/components/common/Game/Dialog/EditRom/{AdditionalDetails,MetadataIdSection,MetadataSections}.vue` (metadata expansion panels inside v2 `EditRomDialog`)
- `frontend/src/components/common/Collection/RAvatar.vue` (collection avatar inside v2 `AddRomsToCollectionDialog`)
- `frontend/src/components/common/Game/AssetCard.vue` (inside v2 `SelectSave/StateDialog` grids)
- `frontend/src/components/Scan/ScanPlatform.vue` (inside v2 `Scan` view expansion body)
- `frontend/src/components/common/{MissingFromFSIcon,Platform/PlatformIcon}.vue` (inside v2 `Scan`/`Patcher` platform pickers)
- Settings sub-components embedded in v2 Settings views: `UserInterface/Interface.vue` (home toggles), `Administration/{UsersTable,TokensTable,Tasks}.vue`, `ClientApiTokens/ClientTokensTable.vue`, `LibraryManagement/Config/{FolderMappings,Excluded,MissingGames}.vue`, `ServerStats/{SummaryStats,PlatformsStats}.vue`, `UserProfile/RetroAchievements.vue`

---

## 6. App-wide services / providers

All wired through `AppLayout.vue` + singleton composables — v2 views should _only_ consume these (never build a parallel channel).

| Service                                 | Provide key               | Consumer composable                                            |
| --------------------------------------- | ------------------------- | -------------------------------------------------------------- |
| Background art cross-fade               | `r-v2-set-background-art` | `useBackgroundArt()`                                           |
| Last input device (mouse/touch/key/pad) | —                         | `useInputModality()` (installs listeners on `AppLayout` mount) |
| UI version toggle                       | —                         | `useUiVersion()` (singleton ref, backs `settings.uiVersion`)   |

AppLayout mounts `<GlobalDialogs />` which hosts every emitter-driven dialog so they overlay every v2 route. All of these are v2-native under `src/v2/components/Dialogs/`, `src/v2/components/Player/`, and `src/v2/components/AppShell/`:

- **Game actions**: `EditRomDialog`, `DeleteRomDialog`, `MatchRomDialog`, `RefreshMetadataDialog`, `ShowQRCodeDialog`, `ManualUploadTargetDialog`, `DeleteManualDialog`
- **Collections**: `AddRomsToCollectionDialog`
- **About**: `AboutDialog`
- **Player**: `SelectSaveDialog`, `SelectStateDialog`, `EmulatorJSCacheDialog`
- **Toasts (still v1)**: `Notification`, `UploadProgress` — same emitter as v1, rebuild scheduled

Any new v2 view that needs a dialog should emit the existing event (`emitter.emit("showFooDialog", payload)`) and either find the dialog already mounted here or add a v2-native one under `src/v2/components/Dialogs/`.

---

## 7. Token reference (current values)

Full list in `src/v2/styles/tokens.css`. Quick hits:

### Color — brand

- `--r-color-brand-primary: #8b74e8`
- `--r-color-brand-primary-hover: #a18fff`
- `--r-color-brand-primary-pressed: #6043c8`
- `--r-color-brand-secondary: #9e8cd6`
- `--r-color-brand-accent: #e1a38d`
- `--r-color-avatar-gradient: linear-gradient(135deg, #a18fff, #6043c8)`
- `--r-color-fav: #ff4f6b` (independent of primary)
- `--r-color-romm-{red,green,blue,gold}` (legacy brand swatches)

### Color — status

- `--r-color-success: #4ade80`, `--r-color-warning: #fbbf24`, `--r-color-danger: #ff5050`, `--r-color-info: #93c5fd`

### Color — surfaces (dark default)

- `--r-color-bg: #07070f`
- `--r-color-bg-elevated: rgba(255,255,255,0.045)`
- `--r-color-surface: rgba(255,255,255,0.07)`
- `--r-color-fg / fg-secondary / fg-muted / fg-faint` at `#fff` / 0.75 / 0.45 / 0.25 alpha
- `--r-color-border / border-strong` at 0.07 / 0.15 alpha

### Typography

- Font: `Segoe UI, -apple-system, BlinkMacSystemFont, system-ui, 'Inter', Roboto, sans-serif`
- `--r-font-size-{xs..4xl}`: 10.5 / 11.5 / 13 / 14.5 / 17 / 22 / 32 / 38 px
- `--r-font-weight-{regular..extrabold}`: 400 / 500 / 600 / 700 / 800
- Line height: `tight 1.1`, `normal 1.4`, `relaxed 1.7`

**Spacing** — 4 px base: `--r-space-{0..14}`. Plus `--r-row-pad: 36px` for page edges.

### Radius

- `--r-radius-xs 3px`, `sm 4px`, `chip 6px`, `md 8px`, `art 8px`, `lg 10px`, `card 14px`, `xl 20px`, `pill 100px`, `full 9999px`

**Elevation** — `--r-elev-{1..5}` scale, plus `--r-elev-cover` for the 240 px detail cover.

**Motion** — `--r-motion-{fast 150ms, med 220ms, slow 360ms}` with `--r-motion-ease-out` + `--r-motion-ease-in-out`.

**Focus modality** — scales the focus ring: `[data-input="mouse"] 2px`, `key 2.5px`, `pad 3.5px`.

**Layout constants** — `--r-nav-h 58px`, `--r-card-art-{w 158, h 213}`, `--r-hero-{w 300, h 169}`, `--r-cover-w 240px`.

---

## 8. Waves — status & next-up

Ticked off relative to `V2_PLAN.md`:

- ✅ Wave 0 — Scaffold + tokens + Storybook
- ✅ Wave 1 — Auth flows (Login / Register / ResetPassword; Setup deferred)
- ✅ Wave 2 — App shell + Home (rewritten in the mockup restyle)
- ✅ Wave 3 — Gallery (Platform / Collection / Search + index pages)
- ✅ Wave 4 — Game Details (hero + tabs, media tab w/ manual + soundtrack)
- ✅ Wave 5 — Players (EmulatorJS + Ruffle — v2 chrome around reused v1 player integrations; SelectSave/SelectState/CacheDialog rebuilt as v2 RDialog variants)
- ✅ Wave 6 — Scan + Patcher + Pair (scan log + live stats, patch dropzones + worker pipeline verbatim, pair via runtime dispatcher)
- ✅ Wave 7 — Settings suite (shared `SettingsShell` + `SettingsNav` pill strip; UserInterface/MetadataSources/UserProfile rebuilt v2-native, rest are v2 chrome around v1 content)
- ✅ Wave 8 — Global dialogs (8 ROM/collection dialogs rebuilt v2-native under `src/v2/components/Dialogs/`: EditRom, DeleteRom, MatchRom, RefreshMetadata, ShowQRCode, ManualUploadTarget, DeleteManual, AddRomsToCollection — glass panels + v2 primitives throughout)
- ✅ Wave 9 — Universal input polish (gamepad → synthetic keyboard translator, modality-gated focus-visible rings, skip-to-content link, `/` + `g h/p/c` hotkeys, `MissingFSBadge` v2 primitive, `PlatformIcon` → `RPlatformIcon` swap across Scan/Patcher)
- ✅ Mockup restyle — full palette/layout pass to match artist design
- ✅ Context menu + user menu + menu library primitives
- ✅ View decomposition pass — GameDetails (967 → 343), Platform (395 → 266), Collection (418 → 295), AppLayout (531 → 115), Login (291 → 99) all split into feature-scoped sub-components under `src/v2/components/<feature>/` (see §4b)
- 🔜 **Wave 10 — Flip default to v2 + delete v1** ← next (blocking on outstanding v1 embeds — see backlog)

- ⬜ Wave 7 — Settings suite
- ⬜ Wave 8 — Global dialogs (rebuild as v2-native replacements for the v1 dialogs we're currently reusing)
- ⬜ Wave 9 — Gamepad / universal input polish
- ⬜ Wave 10 — Flip default to v2 + delete v1

Soundtrack feature branch (`feat/soundtrack-support`) was merged in during Wave 4 so v2 has parity with v1 on manuals + soundtracks.

---

## 9. Known gaps / debt

- `RomMV2.vue` is likely dead code now (AppLayout is the real entry for v2). Sweep it when convenient.
- Mini-player (`SoundtrackMiniPlayer.vue`) is still the v1 component. Hide-on-media-tab logic is wired through URL query params.
- Storybook has stories for every lib primitive; view-level compositions don't have stories (and won't — that's the rule).
- Backend `audio_tags` parsing sometimes fails to pull artist/album for OGG/Vorbis with unusual tag casing — not a frontend issue, flagged here so it's not re-diagnosed in v2 session.

---

## 10. How to add a new view / feature (checklist)

1. If the user describes a visual that doesn't have an R-component, **build the R-component first** (Directive 1.1). Add it to `src/v2/lib/`, export from `src/v2/lib/index.ts`, write at least one story.
2. Add the view under `src/v2/views/…`. Script-setup, small; compose R-components.
3. Register the route in `src/v2/router/routes.ts` under the matching route name.
4. If it's a v2-only route (no v1 equivalent), add it to `src/plugins/router.ts` with `components: { default: fallback, v2: v2For(ROUTES.X) }`.
5. If it needs a new emitter event, check v1 first — most dialog triggers exist. Add the dialog to `AppLayout.vue`'s dialog mounts if missing.
6. If it wants to hook the background art, `const setBg = useBackgroundArt()` and call `setBg(url)` on hover/mount.
7. For a per-ROM action dropdown, drop in `<MoreMenu :rom="rom">` with the trigger button in the `#activator` slot — no app-wide provider needed.
8. Run `npm run typecheck && npm run build` — both must be clean before moving on.
9. Update this guide's §4 (if you added an R-component) and §5 (if you migrated a route).

---

## 11. How to polish an existing view

1. Open the view, read top-to-bottom.
2. For every non-trivial visual block: is it already an R-component? If not and it's repeatable (or the user asks us to reuse it), extract now.
3. When replacing inline CSS with tokens, match the token (never pick raw hex) — if the token doesn't exist yet, add it to `v2/tokens/index.ts` + `v2/styles/tokens.css` first.
4. Match mockup spacings / fonts / radii via token names, not magic numbers.
5. Typecheck + build. Update inventory tables here if needed.
