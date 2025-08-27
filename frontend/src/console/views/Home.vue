<script setup lang="ts">
import { storeToRefs } from "pinia";
import { onMounted, onUnmounted, ref, nextTick, watch } from "vue";
import { useRouter } from "vue-router";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import collectionApi from "@/services/api/collection";
import storeCollections from "@/stores/collections";
import useFavoriteToggle from "@/composables/useFavoriteToggle";
import SystemCard from "@/console/components/SystemCard.vue";
import GameCard from "@/console/components/GameCard.vue";
import CollectionCard from "@/console/components/CollectionCard.vue";
import NavigationHint from "@/console/components/NavigationHint.vue";
import RIsotipo from "@/components/common/RIsotipo.vue";
import type { PlatformSchema } from "@/__generated__/models/PlatformSchema";
import { isSupportedPlatform } from "@/console/constants/platforms";
import type { SimpleRomSchema } from "@/__generated__/models/SimpleRomSchema";
import type { CollectionSchema } from "@/__generated__/models/CollectionSchema";
import { useInputScope } from "@/console/composables/useInputScope";
import type { InputAction } from "@/console/input/actions";
import { useSpatialNav } from "@/console/composables/useSpatialNav";
import { useRovingDom } from "@/console/composables/useRovingDom";
import {
  systemElementRegistry,
  recentElementRegistry,
  collectionElementRegistry,
} from "@/console/composables/useElementRegistry";
import consoleStore from "@/stores/console";
import { ROUTES } from "@/plugins/router";

const router = useRouter();
const collectionsStore = storeCollections();
const storeConsole = consoleStore();
const { navigationMode } = storeToRefs(storeConsole);
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();
const { subscribe } = useInputScope();

const platforms = ref<PlatformSchema[]>([]);
const recent = ref<SimpleRomSchema[]>([]);
const collections = ref<CollectionSchema[]>([]);
const loading = ref(true);
const error = ref("");

// Navigation indices
const selectedIndex = ref(storeConsole.platformIndex);
const recentIndex = ref(storeConsole.recentIndex);
const collectionsIndex = ref(storeConsole.collectionsIndex);
const controlIndex = ref(storeConsole.controlIndex);
const scrollContainerRef = ref<HTMLDivElement>();
const systemsRef = ref<HTMLDivElement>();
const recentRef = ref<HTMLDivElement>();
const collectionsRef = ref<HTMLDivElement>();
const platformsSectionRef = ref<HTMLElement>();
const recentSectionRef = ref<HTMLElement>();
const collectionsSectionRef = ref<HTMLElement>();

const systemElementAt = (i: number) => systemElementRegistry.getElement(i);
const recentElementAt = (i: number) => recentElementRegistry.getElement(i);
const collectionElementAt = (i: number) =>
  collectionElementRegistry.getElement(i);

// Spatial navigation
const { moveLeft: moveSystemLeft, moveRight: moveSystemRight } = useSpatialNav(
  selectedIndex,
  () => platforms.value.length || 1,
  () => platforms.value.length,
);
const { moveLeft: moveRecentLeft, moveRight: moveRecentRight } = useSpatialNav(
  recentIndex,
  () => recent.value.length || 1,
  () => recent.value.length,
);
const { moveLeft: moveCollectionLeft, moveRight: moveCollectionRight } =
  useSpatialNav(
    collectionsIndex,
    () => collections.value.length || 1,
    () => collections.value.length,
  );

useRovingDom(selectedIndex, systemElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false, // handle scrolling manually
});
useRovingDom(recentIndex, recentElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false, // same as above
});
useRovingDom(collectionsIndex, collectionElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false, // same as above
});

// carousel scrolling that respects vertical scroll state
watch(selectedIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = systemElementAt(newIdx);
    if (el && systemsRef.value) {
      centerInCarousel(systemsRef.value, el, "smooth");
    }
  }
});

watch(recentIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = recentElementAt(newIdx);
    if (el && recentRef.value) {
      centerInCarousel(recentRef.value, el, "smooth");
    }
  }
});

watch(collectionsIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = collectionElementAt(newIdx);
    if (el && collectionsRef.value) {
      centerInCarousel(collectionsRef.value, el, "smooth");
    }
  }
});

// Navigation functions
const navigationFunctions = {
  systems: {
    prev: () => {
      const before = selectedIndex.value;
      moveSystemLeft();
      if (selectedIndex.value === before) {
        selectedIndex.value = Math.max(0, platforms.value.length - 1);
      }
    },
    next: () => {
      const before = selectedIndex.value;
      moveSystemRight();
      if (selectedIndex.value === before) {
        selectedIndex.value = 0;
      }
    },
    confirm: () => {
      if (!platforms.value[selectedIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_PLATFORM,
        params: { id: platforms.value[selectedIndex.value].id },
      });
      return true;
    },
  },
  recent: {
    prev: () => {
      const before = recentIndex.value;
      moveRecentLeft();
      if (recentIndex.value === before) {
        recentIndex.value = Math.max(0, recent.value.length - 1);
      }
    },
    next: () => {
      const before = recentIndex.value;
      moveRecentRight();
      if (recentIndex.value === before) {
        recentIndex.value = 0;
      }
    },
    confirm: () => {
      if (!recent.value[recentIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_ROM,
        params: { rom: recent.value[recentIndex.value].id },
        query: { id: recent.value[recentIndex.value].platform_id },
      });
      return true;
    },
  },
  collections: {
    prev: () => {
      const before = collectionsIndex.value;
      moveCollectionLeft();
      if (collectionsIndex.value === before) {
        collectionsIndex.value = Math.max(0, collections.value.length - 1);
      }
    },
    next: () => {
      const before = collectionsIndex.value;
      moveCollectionRight();
      if (collectionsIndex.value === before) {
        collectionsIndex.value = 0;
      }
    },
    confirm: () => {
      if (!collections.value[collectionsIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_COLLECTION,
        params: { id: collections.value[collectionsIndex.value].id },
      });
      return true;
    },
  },
  controls: {
    prev: () => {
      controlIndex.value = (controlIndex.value - 1 + 2) % 2;
    },
    next: () => {
      controlIndex.value = (controlIndex.value + 1) % 2;
    },
    confirm: () => {
      controlIndex.value === 0 ? exitConsoleMode() : toggleFullscreen();
      return true;
    },
  },
};

let verticalScrollPromise: Promise<void> | null = null;
let isVerticalScrolling = false;

function scrollToCurrentRow() {
  isVerticalScrolling = true;

  // promise resolves when the scroll animation finishes
  verticalScrollPromise = new Promise((resolve) => {
    const behavior: ScrollBehavior = "smooth";
    switch (navigationMode.value) {
      case "systems":
        scrollContainerRef.value?.scrollTo({ top: 0, behavior });
        break;
      case "recent":
        recentSectionRef.value?.scrollIntoView({ behavior, block: "start" });
        break;
      case "collections":
        collectionsSectionRef.value?.scrollIntoView({
          behavior,
          block: "start",
        });
        break;
    }

    // resolve after animation
    setTimeout(() => {
      isVerticalScrolling = false;
      verticalScrollPromise = null;
      resolve();
    }, 400); // match smooth scroll duration
  });
}

function centerInCarousel(
  container: HTMLElement | undefined | null,
  el: HTMLElement | undefined | null,
  behavior: ScrollBehavior = "auto",
) {
  if (!container || !el) return;
  if (container.scrollWidth <= container.clientWidth) return;
  const target = el.offsetLeft - (container.clientWidth - el.clientWidth) / 2;
  const targetLeft = Math.max(
    0,
    Math.min(target, container.scrollWidth - container.clientWidth),
  );

  if (behavior === "smooth") {
    container.scrollTo({ left: targetLeft, behavior: "smooth" });
  } else {
    container.scrollLeft = targetLeft;
  }
}

function exitConsoleMode() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  }
  router.push({ name: "home" });
}

function toggleFullscreen() {
  document.fullscreenElement
    ? document.exitFullscreen?.()
    : document.documentElement.requestFullscreen?.();
}

// Navigation handlers
function goPlatform(platformId: number) {
  router.push({ name: ROUTES.CONSOLE_PLATFORM, params: { id: platformId } });
}

function goGame(game: SimpleRomSchema) {
  router.push({
    name: ROUTES.CONSOLE_ROM,
    params: { rom: game.id },
    query: { id: game.platform_id },
  });
}

function goCollection(collectionId: number) {
  router.push({
    name: ROUTES.CONSOLE_COLLECTION,
    params: { id: collectionId },
  });
}

// Input handling
function handleAction(action: InputAction): boolean {
  const currentMode = navigationMode.value;

  switch (action) {
    case "moveLeft":
      if (currentMode in navigationFunctions) {
        navigationFunctions[currentMode].prev();
        return true;
      }
      return false;

    case "moveRight":
      if (currentMode in navigationFunctions) {
        navigationFunctions[currentMode].next();
        return true;
      }
      return false;

    case "moveUp":
      if (currentMode === "systems") {
        navigationMode.value = "controls";
        return true;
      }
      if (currentMode === "recent") {
        navigationMode.value = "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "collections") {
        navigationMode.value = recent.value.length > 0 ? "recent" : "systems";
        scrollToCurrentRow();
        return true;
      }
      return false;

    case "moveDown":
      if (currentMode === "systems") {
        navigationMode.value =
          recent.value.length > 0
            ? "recent"
            : collections.value.length > 0
              ? "collections"
              : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "recent") {
        navigationMode.value =
          collections.value.length > 0 ? "collections" : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "controls") {
        navigationMode.value = "systems";
        return true;
      }
      return false;

    case "confirm":
      if (currentMode in navigationFunctions) {
        return navigationFunctions[currentMode].confirm() ?? false;
      }
      return false;

    case "back":
      return true;

    case "toggleFavorite":
      if (currentMode === "recent" && recent.value[recentIndex.value]) {
        toggleFavoriteComposable(recent.value[recentIndex.value]);
        return true;
      }
      return false;

    default:
      return false;
  }
}

onMounted(async () => {
  try {
    const [{ data: plats }, { data: recents }, { data: cols }] =
      await Promise.all([
        platformApi.getPlatforms(),
        romApi.getRecentPlayedRoms(),
        collectionApi.getCollections(),
      ]);

    platforms.value = plats.filter(
      (p) => p.rom_count > 0 && isSupportedPlatform(p.slug),
    );
    recent.value = recents.items ?? [];
    collections.value = cols ?? [];

    collectionsStore.setCollections(cols ?? []);
    collectionsStore.setFavoriteCollection(
      cols?.find(
        (collection) => collection.name.toLowerCase() === "favourites",
      ),
    );
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to load";
  } finally {
    loading.value = false;
  }

  // Restore indices within bounds
  if (selectedIndex.value >= platforms.value.length) selectedIndex.value = 0;
  if (recentIndex.value >= recent.value.length) recentIndex.value = 0;
  if (collectionsIndex.value >= collections.value.length)
    collectionsIndex.value = 0;

  await nextTick();
  scrollToCurrentRow();

  // Center carousels
  centerInCarousel(systemsRef.value, systemElementAt(selectedIndex.value));
  centerInCarousel(recentRef.value, recentElementAt(recentIndex.value));
  centerInCarousel(
    collectionsRef.value,
    collectionElementAt(collectionsIndex.value),
  );

  off = subscribe(handleAction);
});

let off: (() => void) | null = null;

onUnmounted(() => {
  storeConsole.setHomeState({
    platformIndex: selectedIndex.value,
    recentIndex: recentIndex.value,
    collectionsIndex: collectionsIndex.value,
    controlIndex: controlIndex.value,
    navigationMode: navigationMode.value,
  });
  off?.();
  off = null;
});
</script>

<template>
  <div
    ref="scrollContainerRef"
    class="relative h-screen overflow-y-auto overflow-x-hidden"
    @wheel.prevent
  >
    <div class="relative h-full flex flex-col">
      <div class="mt-8 ml-8 flex items-center gap-3 select-none pb-3">
        <RIsotipo :size="40" :avatar="false" />
        <div class="text-white/90 font-bold text-[28px] drop-shadow-xl">
          Console
        </div>
      </div>

      <div v-if="loading" class="text-center text-fgDim mt-16">
        Loading platforms…
      </div>
      <div v-else-if="error" class="text-center text-red-400 mt-16">
        {{ error }}
      </div>
      <div v-else>
        <section ref="platformsSectionRef" class="pb-2">
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8">
            Platforms
          </h2>
          <div class="relative h-[220px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.systems.prev"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.systems.next"
            >
              ▶
            </button>
            <div
              ref="systemsRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-6 h-full px-12 min-w-max">
                <SystemCard
                  v-for="(p, i) in platforms"
                  :key="p.id"
                  :platform="p"
                  :index="i"
                  :selected="
                    navigationMode === 'systems' && i === selectedIndex
                  "
                  @click="goPlatform(p.id)"
                  @focus="selectedIndex = i"
                />
              </div>
            </div>
          </div>
        </section>

        <section v-if="recent.length > 0" ref="recentSectionRef" class="pb-8">
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8">
            Recently Played
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.recent.prev"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.recent.next"
            >
              ▶
            </button>
            <div
              ref="recentRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <GameCard
                  v-for="(g, i) in recent"
                  :key="`${g.platform_id}-${g.id}`"
                  :rom="g"
                  :index="i"
                  :is-recent="true"
                  :selected="navigationMode === 'recent' && i === recentIndex"
                  :loaded="true"
                  @click="goGame(g)"
                  @focus="recentIndex = i"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="collections.length > 0"
          ref="collectionsSectionRef"
          class="pb-8"
        >
          <h2 class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8">
            Collections
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.collections.prev"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 bg-black/70 border border-white/20 rounded-full flex items-center justify-center text-fg0 cursor-pointer transition-all backdrop-blur z-20 hover:bg-accent2/80 hover:border-accent2"
              @click="navigationFunctions.collections.next"
            >
              ▶
            </button>
            <div
              ref="collectionsRef"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <CollectionCard
                  v-for="(c, i) in collections"
                  :key="`collection-${c.id}`"
                  :collection="c"
                  :index="i"
                  :selected="
                    navigationMode === 'collections' && i === collectionsIndex
                  "
                  :loaded="true"
                  @click="goCollection(c.id)"
                  @focus="collectionsIndex = i"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="fixed top-4 right-4 z-20 flex gap-2">
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="{
            'border-[var(--accent-2)] bg-[var(--accent-2)]/15 shadow-[0_0_0_2px_var(--accent-2),_0_0_18px_-4px_var(--accent-2)] -translate-y-0.5':
              navigationMode === 'controls' && controlIndex === 0,
          }"
          title="Exit Console Mode (F1)"
          @click="exitConsoleMode"
        >
          ⏻
        </button>
        <button
          class="w-12 h-12 bg-black/80 border border-white/20 rounded-md text-fg0 cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:bg-white/10 hover:border-white/40 hover:-translate-y-0.5 hover:shadow-lg"
          :class="{
            'border-[var(--accent-2)] bg-[var(--accent-2)]/15 shadow-[0_0_0_2px_var(--accent-2),_0_0_18px_-4px_var(--accent-2)] -translate-y-0.5':
              navigationMode === 'controls' && controlIndex === 1,
          }"
          title="Fullscreen (F11)"
          @click="toggleFullscreen"
        >
          ⛶
        </button>
      </div>

      <NavigationHint
        :show-back="false"
        :show-toggle-favorite="navigationMode === 'recent'"
      />
    </div>
  </div>
</template>

<style scoped>
button:focus {
  outline: none;
}
</style>
