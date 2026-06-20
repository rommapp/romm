# RomM Frontend Architecture

Comprehensive documentation of the RomM frontend: a Vue 3 single-page application powering the retro gaming platform UI.

---

## Table of Contents

1. [Overview](#1-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Application Lifecycle](#4-application-lifecycle)
5. [Routing & Navigation](#5-routing--navigation)
6. [State Management (Pinia Stores)](#6-state-management-pinia-stores)
7. [API & Data Layer](#7-api--data-layer)
8. [Component Architecture](#8-component-architecture)
9. [Views & Pages](#9-views--pages)
10. [Console Mode](#10-console-mode)
11. [Emulation Integration](#11-emulation-integration)
12. [Theming & Styling](#12-theming--styling)
13. [Internationalization (i18n)](#13-internationalization-i18n)
14. [Real-Time Communication](#14-real-time-communication)
15. [Caching Strategy](#15-caching-strategy)
16. [Utilities & Composables](#16-utilities--composables)
17. [Build & Tooling](#17-build--tooling)
18. [Type System](#18-type-system)

---

## 1. Overview

| Property             | Value                                          |
| -------------------- | ---------------------------------------------- |
| **Framework**        | Vue 3.4.27 (Composition API, `<script setup>`) |
| **Build Tool**       | Vite 6.4.2                                     |
| **Language**         | TypeScript 5.7.3 (`noImplicitAny: true`)       |
| **UI Library**       | Vuetify 3.9.2 (Material Design)                |
| **CSS**              | Tailwind CSS 4.0.0 + Vuetify themes            |
| **State Management** | Pinia 3.0.1 (18 stores)                        |
| **Routing**          | Vue Router 4.3.2                               |
| **HTTP Client**      | Axios 1.15.0                                   |
| **i18n**             | vue-i18n 11.1.10 (17 languages)                |
| **Real-time**        | Socket.IO Client 4.7.5                         |
| **Icons**            | Material Design Icons (MDI) 7.4.47             |
| **Node**             | 24 (via `.nvmrc`)                              |

**Total:** ~216 Vue components (168 under `components/`, rest in views/console/layouts), 18 Pinia stores, 17 API service modules, 36 named routes across 3 layouts.

---

## 2. High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        Browser / PWA                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐   ┌──────────────┐   ┌───────────────────┐   │
│   │  Vue Router  │   │  Pinia Stores │   │   Mitt Emitter    │   │
│   │  (36 routes) │   │  (18 stores)  │   │  (80+ events)     │   │
│   └──────┬──────┘   └──────┬───────┘   └────────┬──────────┘   │
│          │                  │                     │              │
│   ┌──────v──────────────────v─────────────────────v──────────┐  │
│   │                    Components (~216)                       │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │  │
│   │  │  Gallery  │  │ Details  │  │ Settings │  │ Console  │ │  │
│   │  │  Mode     │  │  Page    │  │  Pages   │  │  Mode    │ │  │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │  │
│   └──────────────────────┬───────────────────────────────────┘  │
│                          │                                       │
│   ┌──────────────────────v───────────────────────────────────┐  │
│   │                   Service Layer                           │  │
│   │  ┌─────────┐  ┌───────────┐  ┌──────────┐  ┌─────────┐ │  │
│   │  │  Axios   │  │ Socket.IO │  │  Cache   │  │ Compose │ │  │
│   │  │  API     │  │  Client   │  │ Service  │  │ -ables  │ │  │
│   │  └────┬────┘  └─────┬─────┘  └────┬─────┘  └─────────┘ │  │
│   └───────┼──────────────┼─────────────┼─────────────────────┘  │
│           │              │             │                         │
├───────────┼──────────────┼─────────────┼─────────────────────────┤
│           v              v             v                         │
│     Backend API    WebSocket /ws   Browser Cache API             │
│     (/api/*)       (/ws/socket.io)  (IndexedDB)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Layered Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                     │
│  views/          Page-level route components              │
│  layouts/        Auth, Main, Console layouts              │
│  components/     Feature & common components              │
│  console/        TV/gamepad-optimized UI                  │
├─────────────────────────────────────────────────────────┤
│                    STATE LAYER                            │
│  stores/         18 Pinia stores (auth, roms, config...) │
│  composables/    Reusable stateful logic                  │
├─────────────────────────────────────────────────────────┤
│                    DATA LAYER                             │
│  services/api/   17 Axios-based API modules               │
│  services/cache/ Browser Cache API wrapper                │
│  services/socket Socket.IO client                         │
├─────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                   │
│  plugins/        Vuetify, Pinia, i18n, Router             │
│  styles/         Themes, global CSS                       │
│  locales/        17 language packs                        │
│  types/          TypeScript definitions                   │
│  utils/          Helpers (formatting, emulation, covers)  │
│  __generated__/  OpenAPI-generated types                  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

```text
frontend/
├── index.html                     # HTML entry point (<div id="app">)
├── package.json                   # Dependencies & scripts
├── vite.config.js                 # Vite build config with plugins
├── tsconfig.json                  # TypeScript configuration
├── eslint.config.js               # ESLint flat config
├── .nvmrc                         # Node 24
│
├── assets/                        # Static assets (logos, platform icons)
├── public/                        # Public static files
│
└── src/
    ├── main.ts                    # Entry point: app creation & plugin init
    ├── RomM.vue                   # Root component
    │
    ├── plugins/                   # Vue plugin setup
    │   ├── index.ts               # Plugin registration (Vuetify, Pinia, i18n, Mitt)
    │   ├── router.ts              # Vue Router (36 routes, guards, permissions)
    │   ├── vuetify.ts             # Vuetify instance (themes, icons)
    │   ├── pinia.ts               # Pinia store with router injection
    │   ├── pinia.d.ts             # Pinia type augmentation ($router)
    │   ├── mdeditor.ts            # Markdown editor with XSS plugin
    │   └── transition/            # View Transitions API polyfill
    │
    ├── layouts/                   # Layout wrappers
    │   ├── Auth.vue               # Authentication pages layout
    │   └── Main.vue               # Authenticated pages layout (+ all dialogs)
    │
    ├── views/                     # Page-level components (routes)
    │   ├── Auth/                  # Setup, Login, ResetPassword, Register
    │   ├── Gallery/               # Platform, Search, Collection variants
    │   ├── Player/                # EmulatorJS, RuffleRS
    │   ├── Settings/              # Profile, UI, Library, Metadata, Admin, Stats
    │   ├── Home.vue               # Dashboard
    │   ├── GameDetails.vue        # ROM detail page (8 tabs)
    │   ├── Scan.vue               # Library scan
    │   ├── Patcher.vue            # ROM patcher
    │   ├── Pair.vue               # Device pairing
    │   └── 404.vue                # Not found
    │
    ├── components/                # ~168 Vue components
    │   ├── common/                # Shared, reusable
    │   │   ├── Collection/        # Collection cards, dialogs (9 components)
    │   │   ├── Dialog/            # LoadingDialog, SearchCover
    │   │   ├── EmptyStates/       # 8 empty state variants
    │   │   ├── Game/              # Game cards, dialogs, controls (48+ components)
    │   │   ├── Navigation/        # AppBar, drawers, nav buttons (13 components)
    │   │   ├── Notifications/     # Snackbar, upload progress
    │   │   └── Platform/          # Platform cards, dialogs (8 components)
    │   ├── Details/               # Game detail sub-components (14+)
    │   ├── Gallery/               # Gallery app bar, filters, skeleton
    │   ├── Home/                  # Dashboard sections (8 components)
    │   ├── Scan/                  # Scan platform component
    │   └── Settings/              # Settings sub-components (25+)
    │       ├── Administration/    # Users, tokens, tasks
    │       ├── ClientApiTokens/   # API token list, create, pair
    │       ├── LibraryManagement/ # Platform bindings, exclusions
    │       ├── MetadataSources/   # Provider config & priority
    │       ├── ServerStats/       # Library stats widgets
    │       ├── UserInterface/     # Theme, view, locale
    │       └── UserProfile/       # Profile, password, avatar
    │
    ├── console/                   # Console mode (TV/gamepad UI)
    │   ├── Layout.vue             # Console layout with input bus
    │   ├── index.css              # Console-specific styles
    │   ├── views/                 # Console pages
    │   │   ├── Home.vue           # Platform grid, collections
    │   │   ├── GamesList.vue      # ROM grid for platform/collection
    │   │   ├── Game.vue           # Game details with spatial nav
    │   │   └── Play.vue           # Emulator in console mode
    │   ├── components/            # Console-specific components (12)
    │   │   ├── GameCard.vue, SystemCard.vue, CollectionCard.vue
    │   │   ├── BackButton.vue, NavigationHint.vue
    │   │   ├── ScreenshotLightbox.vue, SettingsModal.vue
    │   │   └── ArrowKeysIcon.vue, DPadIcon.vue, FaceButtons.vue
    │   ├── composables/           # Console-specific composables
    │   │   ├── useConsoleTheme.ts # Theme management
    │   │   ├── useThemeAssets.ts  # Asset path resolution
    │   │   ├── useBackgroundArt.ts # Double-buffered backgrounds
    │   │   ├── useSpatialNav.ts   # Grid navigation
    │   │   ├── useElementRegistry.ts # Focus management
    │   │   ├── useInputScope.ts   # Scoped input handling
    │   │   └── useRovingDom.ts    # ARIA roving tabindex
    │   ├── input/                 # Input system
    │   │   ├── bus.ts             # Stack-based input scope manager
    │   │   ├── actions.ts         # 12 input actions
    │   │   ├── config.ts          # Keyboard + gamepad mappings
    │   │   ├── keyboard.ts        # Keyboard listener
    │   │   └── gamepad.ts         # Gamepad polling (rAF)
    │   ├── constants/             # Console constants (sizes, timings, themes)
    │   └── utils/                 # Console helpers
    │       ├── sfx.ts             # Procedural Web Audio SFX
    │       └── assetResolver.ts   # Theme-aware asset loading
    │
    ├── stores/                    # 18 Pinia stores
    │   ├── auth.ts                # Current user & scopes
    │   ├── roms.ts                # ROM library (largest store, 400+ lines)
    │   ├── platforms.ts           # Platform catalog
    │   ├── collections.ts         # Regular, virtual, smart collections
    │   ├── config.ts              # Server configuration
    │   ├── heartbeat.ts           # Server status & feature flags
    │   ├── galleryFilter.ts       # 13+ filter types
    │   ├── galleryView.ts         # View mode, aspect ratio
    │   ├── navigation.ts          # Drawer & nav state
    │   ├── console.ts             # Console mode navigation indices
    │   ├── scanning.ts            # Scan progress
    │   ├── tasks.ts               # Background task status
    │   ├── upload.ts              # Upload progress tracking
    │   ├── download.ts            # Download queue
    │   ├── playing.ts             # Emulator state
    │   ├── language.ts            # Locale selection
    │   ├── notifications.ts       # Toast queue
    │   └── users.ts               # User list (admin)
    │
    ├── services/                  # Data fetching & communication
    │   ├── api/                   # 16 Axios API modules (+ index.ts client)
    │   │   ├── index.ts           # Axios instance (CSRF, interceptors)
    │   │   ├── rom.ts             # ROM CRUD, upload, download
    │   │   ├── platform.ts        # Platform CRUD
    │   │   ├── collection.ts      # Collection operations
    │   │   ├── user.ts            # User management
    │   │   ├── identity.ts        # Login, logout, password reset
    │   │   ├── config.ts          # Backend configuration
    │   │   ├── task.ts            # Task monitoring
    │   │   ├── firmware.ts        # Firmware uploads
    │   │   ├── save.ts            # Game saves
    │   │   ├── state.ts           # Save states
    │   │   ├── screenshot.ts      # Screenshots
    │   │   ├── setup.ts           # Setup wizard
    │   │   ├── sgdb.ts            # SteamGridDB covers
    │   │   ├── export.ts          # Gamelist.xml + Pegasus exports
    │   │   ├── play-session.ts    # Play session tracking
    │   │   └── client-token.ts    # API token management
    │   ├── cache/                 # Experimental response cache
    │   │   ├── index.ts           # Browser Cache API wrapper
    │   │   └── api.ts             # Cached API service
    │   └── socket.ts              # Socket.IO client
    │
    ├── composables/               # Vue 3 composition utilities
    │   ├── useUISettings.ts       # Settings sync (localStorage ↔ backend)
    │   ├── useFavoriteToggle.ts   # Favorites collection management
    │   ├── useGameAnimation.ts    # CD spin, cartridge load, video hover
    │   └── useAutoScroll.ts       # Auto-scroll on content change
    │
    ├── styles/                    # Global styles
    │   ├── themes.ts              # Dark/light theme definitions
    │   ├── common.css             # Utility classes
    │   ├── fonts.css              # Font definitions
    │   └── scrollbar.css          # Custom scrollbar
    │
    ├── locales/                   # i18n translations
    │   ├── index.ts               # Loader with dynamic imports
    │   ├── en_US/                 # English (default)
    │   ├── en_GB/, fr_FR/, de_DE/, es_ES/, it_IT/, ja_JP/
    │   ├── ko_KR/, pt_BR/, pl_PL/, ro_RO/, ru_RU/
    │   ├── zh_CN/, zh_TW/, cs_CZ/, hu_HU/, bg_BG/
    │   └── (each has: collection, common, console, detail,
    │         emulator, gallery, home, library, login,
    │         navigation, patcher, platform, scan, settings, task)
    │
    ├── types/                     # TypeScript definitions
    │   ├── emitter.d.ts           # 80+ event types
    │   ├── main.d.ts              # Global augmentations
    │   ├── rom.d.ts               # ROM selection types
    │   ├── user.d.ts              # User form types
    │   ├── ruffle.d.ts            # Flash emulator types
    │   ├── rompatcher.d.ts        # ROM patcher types
    │   └── index.ts               # Utility types
    │
    ├── utils/                     # Helper functions
    │   ├── index.ts               # ~825 lines of utilities
    │   ├── covers.ts              # Procedural SVG cover generation
    │   ├── formData.ts            # FormData builder
    │   ├── tasks.ts               # Task status maps
    │   └── indexdb-monitor.ts     # IndexedDB change detection
    │
    └── __generated__/             # OpenAPI codegen output
        └── models/                # Generated TypeScript interfaces
```

---

## 4. Application Lifecycle

### Startup Sequence

```text
index.html
  └── <script type="module" src="src/main.ts">
        │
        ├── Create Vue app with RomM.vue as root
        ├── Register plugins (Vuetify, Pinia, i18n, Mitt, MD Editor)
        ├── Install Vue Router
        │
        ├── Initialize critical stores (before mount):
        │   ├── authStore.fetchCurrentUser()
        │   ├── configStore.fetchConfig()
        │   ├── heartbeatStore.fetchHeartbeat()
        │   └── tasksStore.fetchTasks()
        │
        └── app.mount("#app")
```

### Plugin Registration Order

```text
1. Vuetify     : Material Design components, themes, icons
2. Pinia       : State management (with router injection)
3. vue-i18n    : Internationalization (17 locales)
4. Mitt        : Event emitter (provided as 'emitter')
5. MD Editor   : Markdown editor with XSS plugin
6. Vue Router  : Navigation with guards
```

### Request Lifecycle

```text
Component Action
    │
    ├─ Store Action (e.g., romsStore.fetchRoms())
    │   │
    │   ├─ Cache check (if experimental cache enabled)
    │   │   ├─ Cache hit → return cached, fire background update
    │   │   └─ Cache miss → continue to API
    │   │
    │   ├─ API Service call (e.g., romApi.getRoms(params))
    │   │   │
    │   │   ├─ Axios request interceptor:
    │   │   │   ├─ Add CSRF token (x-csrftoken from cookie)
    │   │   │   └─ Track in inflight set
    │   │   │
    │   │   ├─ HTTP request to /api/*
    │   │   │
    │   │   └─ Axios response interceptor:
    │   │       ├─ Remove from inflight set
    │   │       ├─ 403 → clear session, redirect to login
    │   │       └─ Emit 'network-quiesced' when all requests complete
    │   │
    │   └─ Store mutation (update reactive state)
    │
    └─ Component reacts via reactive refs/getters
```

---

## 5. Routing & Navigation

### Route Map

```text
/ (root)
│
├── Auth Layout (public)
│   ├── /setup                    → Setup wizard (3 steps)
│   ├── /login                    → Login (password + OIDC)
│   ├── /reset-password           → Password reset
│   └── /register                 → Invite-based registration
│
├── /pair                         → Device pairing (standalone, no layout)
│
├── Main Layout (authenticated)
│   ├── /                         → Home dashboard
│   ├── /search                   → Global ROM search
│   ├── /platform/:platform       → Platform gallery
│   ├── /collection/:collection   → Regular collection
│   ├── /collection/virtual/:id   → Virtual collection
│   ├── /collection/smart/:id     → Smart collection
│   ├── /rom/:rom                 → Game details (8 tabs)
│   ├── /rom/:rom/ejs             → EmulatorJS player
│   ├── /rom/:rom/ruffle          → Ruffle Flash player
│   ├── /april-fools              → April Fools easter egg (toggleable)
│   ├── /scan                     → Library scanner [platforms.write]
│   ├── /patcher                  → ROM patcher
│   ├── /user/:user               → User profile
│   ├── /user-interface           → UI settings
│   ├── /library-management       → Library config [platforms.write]
│   ├── /metadata-sources         → Metadata provider status
│   ├── /client-api-tokens        → API token management [me.write]
│   ├── /administration           → User & task admin [users.write]
│   ├── /server-stats             → Library statistics
│   └── /*                        → 404
│
└── Console Layout (authenticated, TV/gamepad)
    ├── /console                  → Console home
    ├── /console/platform/:id     → Console game list
    ├── /console/collection/:id   → Console collection
    ├── /console/collection/smart/:id
    ├── /console/collection/virtual/:id
    ├── /console/rom/:rom         → Console game details
    └── /console/rom/:rom/play    → Console emulator
```

### Route Guards

| Guard                  | Type          | Behavior                                            |
| ---------------------- | ------------- | --------------------------------------------------- |
| Global `beforeEach`    | Navigation    | Setup wizard redirect, auth check, scope validation |
| ROM `beforeEnter`      | Per-route     | Pre-fetches ROM data before rendering               |
| Global `beforeResolve` | Navigation    | View Transitions API animation                      |
| Scroll behavior        | Router config | Restores saved scroll position on back/forward      |

### Permission-Protected Routes

| Route                 | Required Scope    |
| --------------------- | ----------------- |
| `/scan`               | `platforms.write` |
| `/library-management` | `platforms.write` |
| `/client-api-tokens`  | `me.write`        |
| `/administration`     | `users.write`     |

---

## 6. State Management (Pinia Stores)

### Store Overview

```text
┌─────────────────────────────────────────────────────┐
│                   PINIA STORES                       │
├──────────────┬──────────────────────────────────────┤
│ Core Data    │ roms, platforms, collections, users   │
├──────────────┼──────────────────────────────────────┤
│ Auth & Config│ auth, config, heartbeat               │
├──────────────┼──────────────────────────────────────┤
│ UI State     │ navigation, galleryFilter, galleryView│
│              │ language, notifications, console       │
├──────────────┼──────────────────────────────────────┤
│ Operations   │ scanning, tasks, upload, download,    │
│              │ playing                                │
└──────────────┴──────────────────────────────────────┘
```

### Key Stores in Detail

#### `roms` (largest store, ~400 lines)

| State                            | Type                     | Description                      |
| -------------------------------- | ------------------------ | -------------------------------- |
| `_allRoms`                       | `SimpleRom[]`            | Current page of ROMs             |
| `currentPlatform`                | `Platform \| null`       | Active platform filter           |
| `currentCollection`              | `Collection \| null`     | Active collection filter         |
| `currentRom`                     | `DetailedRom \| null`    | Selected ROM details             |
| `recentRoms`                     | `SimpleRom[]`            | Recently added                   |
| `continuePlayingRoms`            | `SimpleRom[]`            | Recently played                  |
| `selectedIDs`                    | `Set<number>`            | Multi-select state               |
| `fetchOffset` / `fetchTotalRoms` | `number`                 | Pagination cursor                |
| `orderBy` / `orderDir`           | `string`                 | Sort (persisted to localStorage) |
| `characterIndex`                 | `Record<string, number>` | A-Z jump index                   |

Key actions: `fetchRoms()`, `fetchRecentRoms()`, `fetchContinuePlayingRoms()`, `add()`, `update()`, `remove()`, `resetPagination()`

#### `galleryFilter`

Manages 13+ filter dimensions with logic operators:

| Filter            | Type              | Logic            |
| ----------------- | ----------------- | ---------------- |
| Genres            | `string[]`        | any / all / none |
| Franchises        | `string[]`        | any / all / none |
| Collections       | `string[]`        | any / all / none |
| Companies         | `string[]`        | any / all / none |
| Age Ratings       | `string[]`        | any / all / none |
| Regions           | `string[]`        | any / all / none |
| Languages         | `string[]`        | any / all / none |
| Player Counts     | `string[]`        | any / all / none |
| Statuses          | `string[]`        | any / all / none |
| Matched           | `boolean \| null` | toggle           |
| Favorites         | `boolean \| null` | toggle           |
| Duplicates        | `boolean \| null` | toggle           |
| Playable          | `boolean \| null` | toggle           |
| RetroAchievements | `boolean \| null` | toggle           |
| Missing           | `boolean \| null` | toggle           |
| Verified          | `boolean \| null` | toggle           |

#### `collections`

Manages three collection types:

| Type     | State                | Description                      |
| -------- | -------------------- | -------------------------------- |
| Regular  | `allCollections`     | User-created collections         |
| Virtual  | `virtualCollections` | Auto-generated by platform/genre |
| Smart    | `smartCollections`   | Filter-criteria based            |
| Favorite | `favoriteCollection` | Special favorite collection      |

#### `heartbeat`

Server capability flags used throughout the UI:

```typescript
METADATA_SOURCES: { IGDB, SS, MOBY, RA, STEAMGRIDDB, LAUNCHBOX, ... }
EMULATION: { DISABLE_EMULATOR_JS, DISABLE_RUFFLE_RS }
FRONTEND: { DISABLE_USERPASS_LOGIN, YOUTUBE_BASE_URL }
OIDC: { ENABLED, AUTOLOGIN, PROVIDER, RP_INITIATED_LOGOUT }
TASKS: { scheduled task configurations }
```

### Persistence Strategy

| Storage                        | What               | Examples                                                    |
| ------------------------------ | ------------------ | ----------------------------------------------------------- |
| **localStorage**               | UI preferences     | View mode, sort order, theme, drawer state, boxart style    |
| **Backend (user.ui_settings)** | Synced preferences | Same as localStorage, synced via `useUISettings` composable |
| **In-memory (Pinia)**          | Session data       | ROMs, platforms, collections, auth state                    |
| **Browser Cache API**          | API responses      | Optional experimental cache with background updates         |

---

## 7. API & Data Layer

### Axios Client Setup

**Location:** `services/api/index.ts`

```typescript
const api = axios.create({
  baseURL: "/api",
  timeout: 120000, // 2 minutes
});
```

**Request Interceptor:**

- Injects CSRF token from `romm_csrftoken` cookie as `x-csrftoken` header
- Tracks inflight requests in a Set

**Response Interceptor:**

- On 403: clears session cookie, refetches CSRF, redirects to `/login`
- Fires `network-quiesced` custom event when all requests complete (250ms debounce)

### API Service Modules

| Module            | Key Endpoints                                    |
| ----------------- | ------------------------------------------------ |
| `rom.ts`          | CRUD, chunked upload, download, search, notes    |
| `collection.ts`   | CRUD for regular/smart/virtual + ROM association |
| `platform.ts`     | CRUD, supported list                             |
| `user.ts`         | CRUD, profile, RA refresh, invite links          |
| `identity.ts`     | Login, logout, forgot/reset password             |
| `config.ts`       | Platform bindings, versions, exclusions          |
| `task.ts`         | List, status, run                                |
| `firmware.ts`     | Upload, list, delete                             |
| `save.ts`         | Upload, update, delete                           |
| `state.ts`        | Upload, update, delete                           |
| `screenshot.ts`   | Upload, update                                   |
| `setup.ts`        | Library structure, platform creation             |
| `sgdb.ts`         | Cover art search                                 |
| `export.ts`       | Gamelist.xml export, Pegasus export              |
| `play-session.ts` | Play session ingestion & listing                 |
| `client-token.ts` | Token CRUD, pair, exchange                       |

### Chunked Upload System (`rom.ts`)

```text
1. POST /roms/upload/start
   Headers: X-Upload-Filename, X-Upload-Total-Size, X-Upload-Total-Chunks
   → Returns upload_id

2. PUT /roms/upload/{upload_id}  (per 10MB chunk)
   Headers: X-Chunk-Number, X-Chunk-Size
   → Retry: 3 attempts with exponential backoff

3. POST /roms/upload/{upload_id}/complete
   → 10-minute timeout for assembly

On failure: POST /roms/upload/{upload_id}/cancel
```

### Key Data Flows

**ROM Gallery Loading:**

```text
Component mount → romsStore.fetchRoms()
  → cachedApiService.getRoms(params, onBackgroundUpdate)
    → Cache hit? Return cached + background refresh
    → API call: GET /api/roms?platform_id=...&limit=72&offset=0&...
  → _postFetchRoms(): update ROMs, pagination, character index, filter values
  → Components react via reactive getters
```

**Filter & Search:**

```text
User sets filter → galleryFilterStore.setSelected*()
  → Component detects change → romsStore.fetchRoms()
    → _buildRequestParams() merges all 13+ filter dimensions
    → API returns filtered paginated results
    → _postFetchRoms() updates available filter values from response
```

**Settings Sync:**

```text
User changes setting → localStorage updated
  → useUISettings watcher fires
    → PUT /api/users/{id} with ui_settings JSON
      → Backend returns updated user
        → authStore.setCurrentUser(data)
          → On next login: user.ui_settings hydrates localStorage
```

---

## 8. Component Architecture

### Organization Pattern

**Feature-based hybrid** with three tiers:

```text
Tier 1: Common (shared, reusable)
├── Collection/     Cards, list items, 6 dialogs
├── Dialog/         Loading, SearchCover
├── EmptyStates/    8 variants (game, platform, collection, firmware, saves...)
├── Game/           Cards, 14 dialogs, PlayBtn, FavBtn, VirtualTable (48+)
├── Navigation/     AppBar, 3 drawers, 10 nav buttons
├── Platform/       Cards, PlatformIcon, 3 dialogs
└── Notifications/  Snackbar, upload progress

Tier 2: Feature-specific
├── Details/        Game detail tabs (14+ sub-components)
├── Gallery/        AppBar variants, filters, skeleton
├── Home/           Dashboard sections (8 components)
├── Scan/           Scan platform component
└── Settings/       25+ settings sub-components

Tier 3: Console Mode
└── console/        12 components + 7 composables + input system
```

### Component Communication

```text
┌─────────────────┐     props/emit     ┌─────────────────┐
│  Parent          │ ←───────────────→ │  Child           │
│  Component       │                    │  Component       │
└────────┬────────┘                    └────────┬────────┘
         │                                       │
    store refs                              store refs
         │                                       │
         v                                       v
┌─────────────────────────────────────────────────────────┐
│                    Pinia Stores                          │
└─────────────────────────────────────────────────────────┘
         │
    mitt events (80+ types)
         │
         v
┌─────────────────────────────────────────────────────────┐
│              Cross-Component Events                      │
│  showEditRomDialog, snackbarShow, playGame, etc.        │
└─────────────────────────────────────────────────────────┘
```

**Patterns used:**

- **Props/emit** for parent-child communication
- **Pinia stores** for shared state across components
- **Mitt emitter** for loosely-coupled cross-component events (dialog triggers, notifications)
- **Provide/inject** for console input scoping

### Dialog System

All dialogs use Vuetify's `v-dialog` wrapped in a custom `RDialog` component:

```text
RDialog (wrapper)
├── Header slot (title + close button)
├── Toolbar slot (optional)
├── Prepend slot
├── Content slot (scrollable)
├── Append slot
└── Footer slot (actions)
```

**15 game dialogs:** EditRom (with 4 sub-components), UploadRom, DeleteRom, MatchRom, NoteDialog, ShowQRCode, CopyDownloadLink, SelectSave, UploadSaves, DeleteSaves, SelectState, UploadStates, DeleteStates

All triggered via Mitt events, rendered in `Main.vue` layout.

---

## 9. Views & Pages

### Home Dashboard (`/`)

| Section             | Data Source                            | Toggleable         |
| ------------------- | -------------------------------------- | ------------------ |
| Stats cards         | `GET /api/stats`                       | Yes (localStorage) |
| Recently added      | `romsStore.fetchRecentRoms()`          | Yes                |
| Continue playing    | `romsStore.fetchContinuePlayingRoms()` | Yes                |
| Platforms grid      | `platformsStore`                       | Yes                |
| Collections         | `collectionsStore`                     | Yes                |
| Smart collections   | `collectionsStore`                     | Yes                |
| Virtual collections | `collectionsStore`                     | Yes                |

### Platform Gallery (`/platform/:platform`)

- Grid or table view (3 sizes + list)
- Infinite scroll pagination (72 per page)
- Multi-select for bulk operations
- 3D tilt effect on cards (vanilla-tilt)
- Virtual table for list mode performance

### Game Details (`/rom/:rom`)

8-tab interface:

| Tab                | Content                           |
| ------------------ | --------------------------------- |
| Details            | File info + game metadata         |
| Manual             | PDF viewer (if available)         |
| Save Data          | Save file management              |
| Personal           | Notes, rating, play time, status  |
| How Long To Beat   | Playtime estimates (if HLTB data) |
| Additional Content | DLC/expansions (mobile)           |
| Related Games      | Remakes/remasters (mobile)        |
| Screenshots        | Screenshot gallery                |

### Scan (`/scan`)

- Platform multi-select
- Metadata source selection with priority ordering
- Real-time progress via Socket.IO
- Log auto-scroll
- Hash calculation toggle

### ROM Patcher (`/patcher`)

Supports: `.ips`, `.ups`, `.bps`, `.ppf`, `.rup`, `.aps`, `.bdf`, `.pmsr`, `.vcdiff`

- Drag-and-drop ROM + patch files
- Platform selection for output
- Save locally or upload to RomM

---

## 10. Console Mode

A complete TV/gamepad-optimized interface under `/console/`.

### Architecture

```text
Console Layout
├── Input Bus (keyboard + gamepad → actions)
├── Theme System (CSS variables per theme)
├── Spatial Navigation (grid-based focus)
├── Sound Effects (Web Audio synthesis)
│
├── Home View
│   ├── Platform cards (spatial nav)
│   ├── Continue playing
│   └── Collections grid
│
├── Games List View
│   ├── Game cards with lazy loading
│   └── Virtual scrolling
│
├── Game Detail View
│   ├── Description, metadata, screenshots
│   ├── Save state management
│   └── Play button → Emulator
│
└── Play View
    └── EmulatorJS with save/state/BIOS selection
```

### Input System

```text
Hardware Input (keyboard / gamepad)
    │
    ├── Keyboard Listener (keydown → action mapping)
    │   └── Ignores when focused on INPUT/TEXTAREA
    │
    ├── Gamepad Poller (requestAnimationFrame loop)
    │   ├── Button press detection (with repeat delay)
    │   └── Analog stick threshold (0.2)
    │
    └── Input Bus (stack-based scope manager)
        ├── Global shortcuts (always active)
        ├── Scoped listeners (context-dependent)
        └── Action dispatch with SFX feedback
```

**12 Input Actions:** `moveUp`, `moveDown`, `moveLeft`, `moveRight`, `confirm`, `back`, `menu`, `delete`, `tabNext`, `tabPrev`, `toggleFavorite`

**Repeat Timing:** 350ms initial delay, 120ms repeat

### Procedural Sound Effects (Web Audio API)

| Sound      | Frequency       | Duration   | When               |
| ---------- | --------------- | ---------- | ------------------ |
| `move`     | 860Hz           | 20ms       | Navigation         |
| `confirm`  | 680→880Hz sweep | 19ms       | Selection          |
| `back`     | 300Hz           | 85ms       | Return             |
| `error`    | 180Hz + 140Hz   | 180ms      | Failure            |
| `delete`   | 260Hz + 180Hz   | 120ms      | Destructive action |
| `favorite` | 600Hz + 950Hz   | Dual burst | Toggle             |

All synthesized with sine/noise blend, exponential envelopes, low-pass filter, and waveshaper saturation.

### Console Composables

| Composable           | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `useSpatialNav`      | Grid navigation with boundary enforcement       |
| `useConsoleTheme`    | Theme CSS variable injection                    |
| `useThemeAssets`     | Format-aware asset resolution (SVG > PNG > JPG) |
| `useBackgroundArt`   | Double-buffered background transitions          |
| `useElementRegistry` | Focus element tracking per section              |
| `useInputScope`      | Dependency-injected input subscription          |
| `useRovingDom`       | ARIA roving tabindex with auto-scroll           |

---

## 11. Emulation Integration

### EmulatorJS

**Location:** `views/Player/EmulatorJS/`

| Feature         | Details                                        |
| --------------- | ---------------------------------------------- |
| Core selection  | Platform-specific core mapping (40+ platforms) |
| BIOS/firmware   | Selectable from uploaded firmware              |
| Save management | Upload, download, delete saves & states        |
| Multi-disc      | Disc selection for multi-file games            |
| Cache           | IndexedDB cache for game data                  |
| Fullscreen      | With keyboard lock                             |
| Netplay         | Socket.IO-based multiplayer                    |
| Controls        | Per-core configurable via config.yml           |

### Ruffle (Flash)

**Location:** `views/Player/RuffleRS/`

- SWF/Flash game emulation via Ruffle 0.2.0-nightly
- Fullscreen support
- Background color customization

### Platform Detection

`utils/index.ts` provides:

- `getSupportedEJSCores(platform)`: maps platforms to EmulatorJS cores
- `isEJSEmulationSupported(rom)`: checks WebGL + server config
- `isRuffleEmulationSupported(rom)`: checks Flash platform
- `isCDBasedSystem(platform)`: 31 CD-based platforms for animation logic

---

## 12. Theming & Styling

### Theme System

**Location:** `styles/themes.ts`

| Theme | Background | Primary   | Accent    |
| ----- | ---------- | --------- | --------- |
| Dark  | `#0D1117`  | `#8B74E8` | `#E1A38D` |
| Light | `#F2F4F8`  | `#371f69` | `#E1A38D` |

**Detection priority:** `settings.theme` localStorage → `prefers-color-scheme` media query → dark default

Vuetify handles theme switching. Additional shared brand colors: `romm-red`, `romm-green`, `romm-blue`, `romm-gold`.

### CSS Stack

| Layer     | Technology                         | Scope                  |
| --------- | ---------------------------------- | ---------------------- |
| Component | Vuetify classes + scoped `<style>` | Per-component          |
| Utility   | Tailwind CSS 4.0                   | Inline utility classes |
| Global    | `styles/common.css`                | App-wide utilities     |
| Scrollbar | `styles/scrollbar.css`             | Custom scrollbar       |
| Console   | `console/index.css`                | Console mode only      |

### Procedural Cover Generation

`utils/covers.ts` generates SVG covers with:

- Hash-based deterministic gradients (consistent per game)
- Collection covers with multi-image grid
- Favorite covers with star icon
- Missing/unmatched covers with icons
- Aspect-ratio-aware empty placeholders

---

## 13. Internationalization (i18n)

### Setup

- **Library:** vue-i18n 11.1.10 (Composition API mode)
- **Locale loading:** Dynamic glob import from `locales/{lang}/*.json`
- **Default:** `en_US`
- **Fallback:** `en_US`

### Supported Languages (17)

| Code    | Language                    |
| ------- | --------------------------- |
| `en_US` | English (US, default)       |
| `en_GB` | English (UK)                |
| `fr_FR` | French                      |
| `de_DE` | German                      |
| `es_ES` | Spanish                     |
| `it_IT` | Italian                     |
| `ja_JP` | Japanese                    |
| `ko_KR` | Korean                      |
| `pt_BR` | Portuguese (Brazil)         |
| `pl_PL` | Polish                      |
| `ro_RO` | Romanian                    |
| `ru_RU` | Russian                     |
| `zh_CN` | Chinese (Simplified)        |
| `zh_TW` | Chinese (Traditional)       |
| `cs_CZ` | Czech (custom plural rules) |
| `hu_HU` | Hungarian                   |
| `bg_BG` | Bulgarian                   |

### Namespace Organization

Each locale directory contains translation files per feature:
`collection`, `common`, `console`, `detail`, `emulator`, `gallery`, `home`, `library`, `login`, `navigation`, `patcher`, `platform`, `scan`, `settings`, `task`

---

## 14. Real-Time Communication

### Socket.IO Client

**Location:** `services/socket.ts`

```typescript
io({
  path: "/ws/socket.io/",
  transports: ["websocket", "polling"],
  autoConnect: false,
});
```

**Usage:** Manually connected during upload and scan operations.

**Events consumed:**

- `scan:update_stats`: live scan progress (platform/ROM counts)
- `scan:log`: scan log messages
- `scan:stop`: scan completion

**Dev proxy:** Vite proxies `/ws` to backend with WebSocket upgrade support.

---

## 15. Caching Strategy

### Experimental Browser Cache

**Location:** `services/cache/`

**Opt-in:** `localStorage.settings.enableExperimentalCache`

```text
Request Flow with Cache:
┌──────────┐    cache hit    ┌──────────┐
│  Component├───────────────→│  Cached   │ → Immediate render
│           │                │  Response │
│           │    meanwhile   │          │
│           │◄───────────────│  Background│ → API fetch
│           │  onBackgroundUpdate       │ → Update if different
└──────────┘                └──────────┘
```

**Features:**

- Browser Cache API (requires HTTPS)
- Request deduplication (concurrent identical requests share promise)
- Background update callbacks (stale-while-revalidate pattern)
- Pattern-based cache clearing
- Used for ROM lists and recent/continue playing data

---

## 16. Utilities & Composables

### Global Composables

| Composable          | Purpose              | Key Features                                                       |
| ------------------- | -------------------- | ------------------------------------------------------------------ |
| `useUISettings`     | Settings persistence | Singleton, localStorage ↔ backend bidirectional sync, 25+ settings |
| `useFavoriteToggle` | Favorites management | Auto-creates Favorites collection, toggle with notifications       |
| `useGameAnimation`  | Card animations      | CD spin (5000 deg/s), cartridge load, video hover (1.5s delay)     |
| `useAutoScroll`     | Scroll management    | Throttled (50ms), mutation observer, respects user scroll          |

### Utility Functions (`utils/index.ts`, ~825 lines)

**Display:**

- `formatBytes()`: human-readable sizes (B through PB)
- `formatTimestamp()`: locale-aware dates
- `formatRelativeDate()`: relative time strings

**Emojis & Localization:**

- `regionToEmoji()`: 50+ region codes → country flags
- `languageToEmoji()`: 40+ language codes → country flags

**Emulation Support:**

- `getSupportedEJSCores()`: platform → EmulatorJS core mapping
- `isEJSEmulationSupported()`: WebGL + config check
- `isCDBasedSystem()`: 31 CD-based platforms

**Game Status:**

- `romStatusMap`: 8 statuses with emoji, text, i18n keys
- Status enum: `unplayed`, `now_playing`, `backlogged`, `paused`, `completed`, `100%`, `retired`, `never_playing`

**Layout:**

- `views`: 3 view modes with responsive grid configurations
- `calculateMainLayoutWidth()`: dynamic width based on drawer state

**Task Display:**

- `convertCronExpression()`: human-readable cron (via cronstrue)
- Task status/type maps with colors and icons

### Cover Generation (`utils/covers.ts`)

Procedural SVG generation for:

- Collection covers (multi-image grid with deterministic gradients)
- Favorite covers (star icon themed)
- Missing covers (question mark icon)
- Unmatched covers (warning icon)
- Empty placeholders (aspect-ratio-aware)

---

## 17. Build & Tooling

### Vite Configuration

| Feature             | Config                                   |
| ------------------- | ---------------------------------------- |
| **Target**          | ESNext                                   |
| **Dev port**        | 3000 (8443 with HTTPS)                   |
| **Backend proxy**   | `/api/*` → `http://127.0.0.1:5000`       |
| **WebSocket proxy** | `/ws`, `/netplay` → backend with upgrade |
| **Allowed hosts**   | `localhost`, `127.0.0.1`, `romm.dev`     |

**Plugins:**

1. Tailwind CSS (`@tailwindcss/vite`)
2. Vue 3 (`@vitejs/plugin-vue`)
3. Vuetify auto-import (`vite-plugin-vuetify`, 57 pre-optimized components)
4. PWA (`vite-plugin-pwa`, service worker, installable)
5. HTTPS (`vite-plugin-mkcert`, optional dev HTTPS)
6. Static copy (ROM patcher JS assets)

### Scripts

| Script      | Command                      | Purpose                             |
| ----------- | ---------------------------- | ----------------------------------- |
| `dev`       | `vite --host`                | Development server                  |
| `build`     | `vite build`                 | Production build                    |
| `preview`   | `vite preview`               | Preview production build            |
| `typecheck` | `vue-tsc`                    | TypeScript validation               |
| `generate`  | `openapi-typescript-codegen` | Generate types from backend OpenAPI |
| `lint`      | `eslint`                     | Lint `.vue`, `.js`, `.ts` files     |

### OpenAPI Code Generation

```bash
npm run generate
# Fetches http://127.0.0.1:3000/openapi.json
# Generates TypeScript interfaces in __generated__/models/
```

Generated types used throughout stores and API services for type-safe backend communication.

### ESLint Configuration

- Flat config (`eslint.config.js`)
- Vue plugin with essential rules
- TypeScript-ESLint integration
- Vue accessibility plugin (`eslint-plugin-vuejs-accessibility`)

---

## 18. Type System

### Generated Types (`__generated__/models/`)

Auto-generated from backend OpenAPI schema:

| Type                                              | Description                                        |
| ------------------------------------------------- | -------------------------------------------------- |
| `SimpleRomSchema`                                 | ROM in list view (covers, metadata IDs, user data) |
| `DetailedRomSchema`                               | Full ROM with all relationships                    |
| `SearchRomSchema`                                 | Minimal search result                              |
| `PlatformSchema`                                  | Platform with ROM count                            |
| `UserSchema`                                      | User with role and settings                        |
| `CollectionSchema`                                | Collection with ROM IDs                            |
| `VirtualCollectionSchema`                         | Auto-generated collection                          |
| `SmartCollectionSchema`                           | Filter-based collection                            |
| `SaveSchema` / `StateSchema` / `ScreenshotSchema` | Asset types                                        |
| `FirmwareSchema`                                  | BIOS file info                                     |
| `HeartbeatResponse`                               | Server status and capabilities                     |
| `ConfigResponse`                                  | Full server configuration                          |
| `ScanStats`                                       | Scan progress counters                             |
| `TaskInfo` / `TaskStatusResponse`                 | Background task data                               |
| `GetRomsResponse`                                 | Paginated ROM list with filter values              |

### Custom Types

| File              | Types                                                  |
| ----------------- | ------------------------------------------------------ |
| `emitter.d.ts`    | `SnackbarStatus`, `Events` (80+ event signatures)      |
| `rom.d.ts`        | `RomSelectEvent`                                       |
| `user.d.ts`       | `UserItem` (extends User with password + avatar)       |
| `ruffle.d.ts`     | `RufflePlayerElement`, `RuffleSourceAPI`               |
| `rompatcher.d.ts` | ROM patching library interfaces                        |
| `main.d.ts`       | Global augmentations                                   |
| `index.ts`        | `isKeyof<T>`, `ExtractPiniaStoreType<D>`, `ValueOf<T>` |

### Path Alias

```json
"@/*" → "./src/*"
```

Used throughout: `import { ... } from "@/stores/roms"`.

---

## Appendix: Key Design Patterns

| Pattern                    | Where                  | Purpose                                          |
| -------------------------- | ---------------------- | ------------------------------------------------ |
| **Composition API**        | All components         | `<script setup>` with reactive refs              |
| **Pinia stores**           | `stores/`              | Centralized state with actions/getters           |
| **Mitt event bus**         | Cross-component        | Loosely-coupled dialog/notification triggers     |
| **Composables**            | `composables/`         | Reusable stateful logic (singleton where needed) |
| **Stale-while-revalidate** | `services/cache/`      | Return cached, update in background              |
| **Chunked upload**         | `services/api/rom.ts`  | 10MB chunks with retry                           |
| **Spatial navigation**     | `console/`             | Grid-based focus for gamepad/keyboard            |
| **Input scoping**          | `console/input/bus.ts` | Stack-based context for input handling           |
| **Procedural audio**       | `console/utils/sfx.ts` | Web Audio API synthesis                          |
| **Double buffering**       | `useBackgroundArt`     | Smooth background transitions                    |
| **View Transitions**       | `plugins/transition/`  | CSS View Transitions API                         |
| **OpenAPI codegen**        | `__generated__/`       | Type-safe API communication                      |
| **Feature flags**          | `heartbeatStore`       | Server-driven UI feature toggling                |
