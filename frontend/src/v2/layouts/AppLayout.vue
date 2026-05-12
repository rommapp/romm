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
import { onBeforeUnmount, onMounted, provide, ref } from "vue";
import { useRouter } from "vue-router";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import AppNav from "@/v2/components/AppShell/AppNav.vue";
import BackgroundArt from "@/v2/components/AppShell/BackgroundArt.vue";
import GlobalDialogs from "@/v2/components/AppShell/GlobalDialogs.vue";
import { BACKGROUND_ART_KEY } from "@/v2/composables/useBackgroundArt";
import { installPermissionsHydration } from "@/v2/composables/useCan";
import { useGamepad } from "@/v2/composables/useGamepad";
import { useGlobalHotkeys } from "@/v2/composables/useGlobalHotkeys";
import { useInputModality } from "@/v2/composables/useInputModality";
import { prefetchPlatformIcons } from "@/v2/composables/usePlatformIconCache";
import { installBackMorph } from "@/v2/composables/useViewTransition";

installPermissionsHydration();

const collectionsStore = storeCollections();
const platformsStore = storePlatforms();

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
});

onBeforeUnmount(() => {
  removeBackMorph?.();
  removeBackMorph = null;
  if (bgTimer !== null) {
    clearTimeout(bgTimer);
    bgTimer = null;
  }
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
    </div>

    <GlobalDialogs />
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
  min-height: 100vh;
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
</style>
