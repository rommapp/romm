<script setup lang="ts">
// AppLayout — top-level v2 shell. Thin orchestrator: owns the background-art
// provider and mounts the visual chrome.
//
//   * BackgroundArt — two-layer blurred backdrop with cross-fade
//   * AppNav        — logo · centred tab pill · user menu
//   * GlobalDialogs — emitter-driven dialog + notification stack
//
// Per-ROM action menus are not app-wide: each GameCard owns its own
// `MoreMenu` dropdown on the three-dots button. Right-click is left to
// the browser so "Open in new tab" etc. keep working.
import {
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  provide,
  ref,
  watch,
} from "vue";
import { useRouter } from "vue-router";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import { useStreamingStore } from "@/stores/streaming";
import AppNav from "@/v2/components/AppShell/AppNav.vue";
import BackgroundArt from "@/v2/components/AppShell/BackgroundArt.vue";
import BottomNav from "@/v2/components/AppShell/BottomNav.vue";
import CrtOverlay from "@/v2/components/AppShell/CrtOverlay.vue";
import GlobalDialogs from "@/v2/components/Dialogs/GlobalDialogs.vue";
import SoundtrackMiniPlayer from "@/v2/components/Soundtrack/MiniPlayer.vue";
import { BACKGROUND_ART_KEY } from "@/v2/composables/useBackgroundArt";
import { installBreakpointAttribute } from "@/v2/composables/useBreakpoint";
import { installPermissionsHydration } from "@/v2/composables/useCan";
import { useDebugMode } from "@/v2/composables/useDebugMode";
import { useGamepad } from "@/v2/composables/useGamepad";
import { useGlobalHotkeys } from "@/v2/composables/useGlobalHotkeys";
import { useInputModality } from "@/v2/composables/useInputModality";
import { prefetchPlatformIcons } from "@/v2/composables/usePlatformIconCache";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import { installScanLifecycle } from "@/v2/composables/useScanLifecycle";
import { installBackMorph } from "@/v2/composables/useViewTransition";

installPermissionsHydration();
// Global scan socket → store wiring so `scanning` flips back to false on
// `scan:done` / `scan:done_ko` and `scanStats` keeps ticking from any
// route the user is on (navbar indicator + /scan view consume the same
// store state).
installScanLifecycle();
// Mirror useBreakpoint() refs onto <html data-bp="…"> so scoped styles
// can branch on viewport via `html[data-bp~="xs"] .foo { … }` instead of
// hardcoding `@media (max-width: …)` values across every SFC.
installBreakpointAttribute();

// Reduced-motion mode: mirror the flag onto <html> so global CSS can drop
// its heaviest work via `html.r-v2-reduced-motion .foo { … }` (background-art
// blur, cover blur-up, the global animation/transition neutralize). On <html>
// (not the shell root) for the same reason as the theme classes: Vuetify
// teleports overlays outside the app tree, and this keeps the flag reachable
// there too.
const { enabled: reducedMotion } = useReducedMotion();
watch(
  reducedMotion,
  (on) => {
    document.documentElement.classList.toggle("r-v2-reduced-motion", on);
  },
  { immediate: true },
);

const collectionsStore = storeCollections();
const platformsStore = storePlatforms();
const streamingStore = useStreamingStore();

// Developer debug overlay — opt-in via Settings → Developer (per-device).
// Lazily loaded so its chunk (and the vueuse perf hooks it pulls in) is only
// fetched once the toggle is on, keeping it out of the default bundle.
const { enabled: debugEnabled } = useDebugMode();
const DebugOverlay = defineAsyncComponent(
  () => import("@/v2/components/AppShell/DebugOverlay.vue"),
);

// Shared reactive background art — views paint covers via the injected setter.
const layerA = ref<string | null>(null);
const layerB = ref<string | null>(null);
const activeLayer = ref<"a" | "b">("a");

// Dwell before applying a backdrop swap. Without it, dragging the cursor
// across the gallery would trigger one cross-fade per card and the
// 700ms fades collide as flashes; the latest call wins after the dwell.
const BG_HOVER_DWELL_MS = 80;
let bgTimer: ReturnType<typeof setTimeout> | null = null;

function setBackgroundArt(url: string | null) {
  const current = activeLayer.value === "a" ? layerA.value : layerB.value;
  if (current === url) {
    if (bgTimer !== null) {
      clearTimeout(bgTimer);
      bgTimer = null;
    }
    return;
  }
  if (bgTimer !== null) clearTimeout(bgTimer);
  bgTimer = setTimeout(() => {
    bgTimer = null;
    if (activeLayer.value === "a") {
      layerB.value = url;
      activeLayer.value = "b";
    } else {
      layerA.value = url;
      activeLayer.value = "a";
    }
  }, BG_HOVER_DWELL_MS);
}
provide(BACKGROUND_ART_KEY, setBackgroundArt);

const { install: installInputModality } = useInputModality();
const { install: installGamepad } = useGamepad();
const { install: installGlobalHotkeys } = useGlobalHotkeys();
const router = useRouter();

let removeBackMorph: (() => void) | null = null;

onMounted(() => {
  installInputModality();
  installGamepad();
  installGlobalHotkeys();
  // Mirror morph: GameDetails cover → destination card on back/navbar/popstate.
  // Forward direction is handled at the source side in GameCard.
  removeBackMorph = installBackMorph(router);
  // Hydrate collections (incl. favoriteCollection) so per-ROM favorite
  // state resolves on direct navigation to /rom/:id without going
  // through Home / Collections first. v1 did this in `Main.vue`.
  if (collectionsStore.allCollections.length === 0) {
    void collectionsStore.fetchCollections();
  }
  // Hydrate platforms for the same reason — views like MissingGames,
  // GameDetails, etc. read `platformsStore.get(id)` to resolve a
  // platform's display name and slug. Without this, direct loads of
  // those views in v2 see undefined slugs and icons fall through to
  // `default.ico`. v1 ran this in `Main.vue`; v2's AppLayout owns the
  // same responsibility. Once the store is populated, kick off a
  // background prefetch of every platform's icon so the in-memory
  // blob cache is ready by the time any picker / table renders.
  if (platformsStore.allPlatforms.length === 0) {
    void platformsStore.fetchPlatforms().then(() => {
      prefetchPlatformIcons(platformsStore.allPlatforms.map((p) => p.slug));
    });
  } else {
    prefetchPlatformIcons(platformsStore.allPlatforms.map((p) => p.slug));
  }

  // Streaming config is fetched once on app load
  void streamingStore.fetchConfig();
});

onBeforeUnmount(() => {
  removeBackMorph?.();
  removeBackMorph = null;
  if (bgTimer !== null) {
    clearTimeout(bgTimer);
    bgTimer = null;
  }
  // Leaving v2 (e.g. switching back to the v1 UI): drop the root flag so
  // the class doesn't linger on a non-v2 document.
  document.documentElement.classList.remove("r-v2-reduced-motion");
});
</script>

<template>
  <div class="r-v2-shell">
    <BackgroundArt
      :layer-a="layerA"
      :layer-b="layerB"
      :active-layer="activeLayer"
    />

    <div class="r-v2-shell__app">
      <AppNav />
      <main id="r-v2-main" class="r-v2-shell__main" tabindex="-1">
        <router-view name="v2" />
      </main>
      <BottomNav />
    </div>

    <GlobalDialogs />
    <SoundtrackMiniPlayer />
    <DebugOverlay v-if="debugEnabled" />
    <CrtOverlay />
  </div>
</template>

<style scoped>
/* The shell flows naturally so the document scrollbar is the single,
   active scrollbar of the app. AppNav is `position: fixed` (defined
   in its own SFC) and main reserves the navbar's height with a top
   padding so content starts right under it.
     · Views that fit within `100vh - --r-nav-h` (Gallery — its own
       shell already uses that calc and `overflow: hidden`; GameDetails
       uses the same calc with an internal panel scroll) generate no
       document overflow → no document scrollbar on those routes.
     · Views with natural flow (Home, Settings, Patcher, Scan, etc.)
       grow with content and the document scrolls. */
.r-v2-shell {
  color: var(--r-color-fg);
  position: relative;
  /* `dvh` tracks the mobile visible viewport (address bar shown/hidden).
     `vh` (the large viewport) leaves the app taller than the screen while
     the bar is visible, forcing a second, document-level scroll on top of
     a view's internal scroll. */
  min-height: 100vh;
  min-height: 100dvh;
}

.r-v2-shell__app {
  position: relative;
  z-index: 2;
}

.r-v2-shell__main {
  position: relative;
  padding-top: var(--r-nav-h);
  outline: none;
}

/* On sm-and-down the fixed bottom tab bar (BottomNav) overlays the
   bottom edge — reserve its height (+ safe-area inset) so natural-flow
   views (Home, Settings, Library Tools, …) can scroll their last content
   clear of the bar. Fixed-height views with their own internal scroll
   (galleries) subtract the same amount from their height calc so the
   totals still sum to one viewport with no document overflow. */
html[data-bp~="sm-and-down"] .r-v2-shell__main {
  padding-bottom: calc(var(--r-bottom-nav-h) + env(safe-area-inset-bottom));
}
</style>
