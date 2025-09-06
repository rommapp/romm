<script setup lang="ts">
import { storeToRefs } from "pinia";
import {
  onMounted,
  onUnmounted,
  ref,
  nextTick,
  watch,
  useTemplateRef,
} from "vue";
import { useRouter } from "vue-router";
import type { CollectionSchema } from "@/__generated__/models/CollectionSchema";
import type { PlatformSchema } from "@/__generated__/models/PlatformSchema";
import type { SmartCollectionSchema } from "@/__generated__/models/SmartCollectionSchema";
import type { VirtualCollectionSchema } from "@/__generated__/models/VirtualCollectionSchema";
import RIsotipo from "@/components/common/RIsotipo.vue";
import useFavoriteToggle from "@/composables/useFavoriteToggle";
import CollectionCard from "@/console/components/CollectionCard.vue";
import GameCard from "@/console/components/GameCard.vue";
import NavigationHint from "@/console/components/NavigationHint.vue";
import SettingsModal from "@/console/components/SettingsModal.vue";
import SystemCard from "@/console/components/SystemCard.vue";
import useBackgroundArt from "@/console/composables/useBackgroundArt";
import {
  systemElementRegistry,
  recentElementRegistry,
  collectionElementRegistry,
  smartCollectionElementRegistry,
  virtualCollectionElementRegistry,
} from "@/console/composables/useElementRegistry";
import { useInputScope } from "@/console/composables/useInputScope";
import { useRovingDom } from "@/console/composables/useRovingDom";
import { useSpatialNav } from "@/console/composables/useSpatialNav";
import { isSupportedPlatform } from "@/console/constants/platforms";
import type { InputAction } from "@/console/input/actions";
import { ROUTES } from "@/plugins/router";
import collectionApi from "@/services/api/collection";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import consoleStore from "@/stores/console";
import type { SimpleRom } from "@/stores/roms";

const router = useRouter();
const collectionsStore = storeCollections();
const storeConsole = consoleStore();
const { navigationMode } = storeToRefs(storeConsole);
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();
const { setSelectedBackgroundArt, clearSelectedBackgroundArt } =
  useBackgroundArt();
const { subscribe } = useInputScope();

const platforms = ref<PlatformSchema[]>([]);
const recentRoms = ref<SimpleRom[]>([]);
const collections = ref<CollectionSchema[]>([]);
const smartCollections = ref<SmartCollectionSchema[]>([]);
const virtualCollections = ref<VirtualCollectionSchema[]>([]);
const loadingPlatforms = ref(true);
const errorMessage = ref("");
const showSettings = ref(false);

// Navigation indices
const platformIndex = ref(storeConsole.platformIndex);
const recentIndex = ref(storeConsole.recentIndex);
const collectionsIndex = ref(storeConsole.collectionsIndex);
const smartCollectionsIndex = ref(storeConsole.smartCollectionsIndex);
const virtualCollectionsIndex = ref(storeConsole.virtualCollectionsIndex);
const controlIndex = ref(storeConsole.controlIndex);
const scrollContainerRef = useTemplateRef<HTMLDivElement>(
  "scroll-container-ref",
);
const platformsRef = useTemplateRef<HTMLDivElement>("platforms-ref");
const recentRef = useTemplateRef<HTMLDivElement>("recent-ref");
const collectionsRef = useTemplateRef<HTMLDivElement>("collections-ref");
const smartCollectionsRef = useTemplateRef<HTMLDivElement>(
  "smart-collections-ref",
);
const virtualCollectionsRef = useTemplateRef<HTMLDivElement>(
  "virtual-collections-ref",
);
const recentSectionRef = useTemplateRef<HTMLElement>("recent-section-ref");
const collectionsSectionRef = useTemplateRef<HTMLElement>(
  "collections-section-ref",
);
const smartCollectionsSectionRef = useTemplateRef<HTMLElement>(
  "smart-collections-section-ref",
);
const virtualCollectionsSectionRef = useTemplateRef<HTMLElement>(
  "virtual-collections-section-ref",
);

const systemElementAt = (i: number) => systemElementRegistry.getElement(i);
const recentElementAt = (i: number) => recentElementRegistry.getElement(i);
const collectionElementAt = (i: number) =>
  collectionElementRegistry.getElement(i);
const smartCollectionElementAt = (i: number) =>
  smartCollectionElementRegistry.getElement(i);
const virtualCollectionElementAt = (i: number) =>
  virtualCollectionElementRegistry.getElement(i);

// Spatial navigation
const { moveLeft: moveSystemLeft, moveRight: moveSystemRight } = useSpatialNav(
  platformIndex,
  () => platforms.value.length || 1,
  () => platforms.value.length,
);
const { moveLeft: moveRecentLeft, moveRight: moveRecentRight } = useSpatialNav(
  recentIndex,
  () => recentRoms.value.length || 1,
  () => recentRoms.value.length,
);
const { moveLeft: moveCollectionLeft, moveRight: moveCollectionRight } =
  useSpatialNav(
    collectionsIndex,
    () => collections.value.length || 1,
    () => collections.value.length,
  );
const {
  moveLeft: moveSmartCollectionLeft,
  moveRight: moveSmartCollectionRight,
} = useSpatialNav(
  smartCollectionsIndex,
  () => smartCollections.value.length || 1,
  () => smartCollections.value.length,
);
const {
  moveLeft: moveVirtualCollectionLeft,
  moveRight: moveVirtualCollectionRight,
} = useSpatialNav(
  virtualCollectionsIndex,
  () => virtualCollections.value.length || 1,
  () => virtualCollections.value.length,
);

useRovingDom(platformIndex, systemElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false, // handle scrolling manually
});
useRovingDom(recentIndex, recentElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false,
});
useRovingDom(collectionsIndex, collectionElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false,
});
useRovingDom(smartCollectionsIndex, smartCollectionElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false,
});
useRovingDom(virtualCollectionsIndex, virtualCollectionElementAt, {
  inline: "center",
  block: "nearest",
  behavior: "smooth",
  scroll: false,
});

// carousel scrolling that respects vertical scroll state
watch(platformIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = systemElementAt(newIdx);
    if (el && platformsRef.value) {
      centerInCarousel(platformsRef.value, el, "smooth");
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

watch(smartCollectionsIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = smartCollectionElementAt(newIdx);
    if (el && smartCollectionsRef.value) {
      centerInCarousel(smartCollectionsRef.value, el, "smooth");
    }
  }
});

watch(virtualCollectionsIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = virtualCollectionElementAt(newIdx);
    if (el && virtualCollectionsRef.value) {
      centerInCarousel(virtualCollectionsRef.value, el, "smooth");
    }
  }
});

// Navigation functions
const navigationFunctions = {
  systems: {
    prev: () => {
      const before = platformIndex.value;
      moveSystemLeft();
      if (platformIndex.value === before) {
        platformIndex.value = Math.max(0, platforms.value.length - 1);
      }
    },
    next: () => {
      const before = platformIndex.value;
      moveSystemRight();
      if (platformIndex.value === before) {
        platformIndex.value = 0;
      }
    },
    confirm: () => {
      if (!platforms.value[platformIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_PLATFORM,
        params: { id: platforms.value[platformIndex.value].id },
      });
      return true;
    },
  },
  recent: {
    prev: () => {
      const before = recentIndex.value;
      moveRecentLeft();
      if (recentIndex.value === before) {
        recentIndex.value = Math.max(0, recentRoms.value.length - 1);
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
      if (!recentRoms.value[recentIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_ROM,
        params: { rom: recentRoms.value[recentIndex.value].id },
        query: { id: recentRoms.value[recentIndex.value].platform_id },
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
  smartCollections: {
    prev: () => {
      const before = smartCollectionsIndex.value;
      moveSmartCollectionLeft();
      if (smartCollectionsIndex.value === before) {
        smartCollectionsIndex.value = Math.max(
          0,
          smartCollections.value.length - 1,
        );
      }
    },
    next: () => {
      const before = smartCollectionsIndex.value;
      moveSmartCollectionRight();
      if (smartCollectionsIndex.value === before) {
        smartCollectionsIndex.value = 0;
      }
    },
    confirm: () => {
      if (!smartCollections.value[smartCollectionsIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_SMART_COLLECTION,
        params: { id: smartCollections.value[smartCollectionsIndex.value].id },
      });
      return true;
    },
  },
  virtualCollections: {
    prev: () => {
      const before = virtualCollectionsIndex.value;
      moveVirtualCollectionLeft();
      if (virtualCollectionsIndex.value === before) {
        virtualCollectionsIndex.value = Math.max(
          0,
          virtualCollections.value.length - 1,
        );
      }
    },
    next: () => {
      const before = virtualCollectionsIndex.value;
      moveVirtualCollectionRight();
      if (virtualCollectionsIndex.value === before) {
        virtualCollectionsIndex.value = 0;
      }
    },
    confirm: () => {
      if (!virtualCollections.value[virtualCollectionsIndex.value])
        return false;
      router.push({
        name: ROUTES.CONSOLE_VIRTUAL_COLLECTION,
        params: {
          id: virtualCollections.value[virtualCollectionsIndex.value].id,
        },
      });
      return true;
    },
  },
  controls: {
    prev: () => {
      controlIndex.value = (controlIndex.value - 1 + 3) % 3;
    },
    next: () => {
      controlIndex.value = (controlIndex.value + 1) % 3;
    },
    confirm: () => {
      if (controlIndex.value === 0) {
        exitConsoleMode();
      } else if (controlIndex.value === 1) {
        toggleFullscreen();
      } else if (controlIndex.value === 2) {
        showSettings.value = true;
      }
      return true;
    },
  },
};

let verticalScrollPromise: Promise<void> | null = null;
let isVerticalScrolling = false;

function scrollToCurrentRow() {
  isVerticalScrolling = true;

  // clear background art when switching sections
  clearSelectedBackgroundArt();

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
      case "smartCollections":
        smartCollectionsSectionRef.value?.scrollIntoView({
          behavior,
          block: "start",
        });
        break;
      case "virtualCollections":
        virtualCollectionsSectionRef.value?.scrollIntoView({
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
  router.push({ name: ROUTES.HOME });
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

function goGame(game: SimpleRom) {
  router.push({
    name: ROUTES.CONSOLE_ROM,
    params: { rom: game.id },
    query: { id: game.platform_id },
  });
}

function handleItemSelected(coverUrl: string) {
  setSelectedBackgroundArt(coverUrl);
}

function handleItemDeselected() {
  clearSelectedBackgroundArt();
}

function goCollection(collectionId: number) {
  router.push({
    name: ROUTES.CONSOLE_COLLECTION,
    params: { id: collectionId },
  });
}

function goSmartCollection(collectionId: number) {
  router.push({
    name: ROUTES.CONSOLE_SMART_COLLECTION,
    params: { id: collectionId },
  });
}

function goVirtualCollection(collectionId: string) {
  router.push({
    name: ROUTES.CONSOLE_VIRTUAL_COLLECTION,
    params: { id: collectionId },
  });
}

// Input handling
function handleAction(action: InputAction): boolean {
  // settings modal handling
  if (showSettings.value) {
    if (action === "back") {
      showSettings.value = false;
      return true;
    }
    // the modal handles the other actions
    return false;
  }

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
        navigationMode.value =
          recentRoms.value.length > 0 ? "recent" : "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "smartCollections") {
        navigationMode.value =
          collections.value.length > 0
            ? "collections"
            : recentRoms.value.length > 0
              ? "recent"
              : "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "virtualCollections") {
        navigationMode.value =
          smartCollections.value.length > 0
            ? "smartCollections"
            : collections.value.length > 0
              ? "collections"
              : recentRoms.value.length > 0
                ? "recent"
                : "systems";
        scrollToCurrentRow();
        return true;
      }
      return false;

    case "moveDown":
      if (currentMode === "systems") {
        navigationMode.value =
          recentRoms.value.length > 0
            ? "recent"
            : collections.value.length > 0
              ? "collections"
              : smartCollections.value.length > 0
                ? "smartCollections"
                : virtualCollections.value.length > 0
                  ? "virtualCollections"
                  : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "recent") {
        navigationMode.value =
          collections.value.length > 0
            ? "collections"
            : smartCollections.value.length > 0
              ? "smartCollections"
              : virtualCollections.value.length > 0
                ? "virtualCollections"
                : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "collections") {
        navigationMode.value =
          smartCollections.value.length > 0
            ? "smartCollections"
            : virtualCollections.value.length > 0
              ? "virtualCollections"
              : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "smartCollections") {
        navigationMode.value =
          virtualCollections.value.length > 0
            ? "virtualCollections"
            : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "virtualCollections") {
        navigationMode.value = "controls";
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
      if (currentMode === "recent" && recentRoms.value[recentIndex.value]) {
        toggleFavoriteComposable(recentRoms.value[recentIndex.value]);
        return true;
      }
      return false;

    default:
      return false;
  }
}

onMounted(async () => {
  try {
    const [
      { data: plats },
      { data: recents },
      { data: cols },
      { data: smartCols },
      { data: virtualCols },
    ] = await Promise.all([
      platformApi.getPlatforms(),
      romApi.getRecentPlayedRoms(),
      collectionApi.getCollections(),
      collectionApi.getSmartCollections(),
      collectionApi.getVirtualCollections({ type: "collection" }),
    ]);

    platforms.value = plats.filter(
      (p) => p.rom_count > 0 && isSupportedPlatform(p.slug),
    );
    recentRoms.value = recents.items ?? [];
    collections.value = cols ?? [];
    smartCollections.value = smartCols ?? [];
    virtualCollections.value = virtualCols ?? [];

    collectionsStore.setCollections(cols ?? []);
    collectionsStore.setFavoriteCollection(
      cols?.find(
        (collection) => collection.name.toLowerCase() === "favourites",
      ),
    );
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error ? err.message : "Failed to load";
  } finally {
    loadingPlatforms.value = false;
  }

  // Restore indices within bounds
  if (platformIndex.value >= platforms.value.length) platformIndex.value = 0;
  if (recentIndex.value >= recentRoms.value.length) recentIndex.value = 0;
  if (collectionsIndex.value >= collections.value.length)
    collectionsIndex.value = 0;
  if (smartCollectionsIndex.value >= smartCollections.value.length)
    smartCollectionsIndex.value = 0;
  if (virtualCollectionsIndex.value >= virtualCollections.value.length)
    virtualCollectionsIndex.value = 0;

  await nextTick();
  scrollToCurrentRow();

  // Center carousels
  centerInCarousel(platformsRef.value, systemElementAt(platformIndex.value));
  centerInCarousel(recentRef.value, recentElementAt(recentIndex.value));
  centerInCarousel(
    collectionsRef.value,
    collectionElementAt(collectionsIndex.value),
  );
  centerInCarousel(
    smartCollectionsRef.value,
    smartCollectionElementAt(smartCollectionsIndex.value),
  );
  centerInCarousel(
    virtualCollectionsRef.value,
    virtualCollectionElementAt(virtualCollectionsIndex.value),
  );

  off = subscribe(handleAction);
});

let off: (() => void) | null = null;

onUnmounted(() => {
  storeConsole.setHomeState({
    platformIndex: platformIndex.value,
    recentIndex: recentIndex.value,
    collectionsIndex: collectionsIndex.value,
    smartCollectionsIndex: smartCollectionsIndex.value,
    virtualCollectionsIndex: virtualCollectionsIndex.value,
    controlIndex: controlIndex.value,
    navigationMode: navigationMode.value,
  });
  off?.();
  off = null;
});
</script>

<template>
  <div
    ref="scroll-container-ref"
    class="relative h-screen overflow-y-auto overflow-x-hidden"
    @wheel.prevent
  >
    <div class="relative h-full flex flex-col">
      <div class="mt-8 ml-8 flex items-center gap-3 select-none pb-3">
        <RIsotipo :size="40" :avatar="false" />
        <div
          class="font-bold text-[28px] drop-shadow-xl"
          :style="{ color: 'var(--console-home-title-text)' }"
        >
          Console
        </div>
      </div>

      <div
        v-if="loadingPlatforms"
        class="text-center mt-16"
        :style="{ color: 'var(--console-loading-text)' }"
      >
        Loading platforms…
      </div>
      <div
        v-else-if="errorMessage"
        class="text-center mt-16"
        :style="{ color: 'var(--console-errorMessage-text)' }"
      >
        {{ errorMessage }}
      </div>
      <div v-else>
        <section class="pb-2">
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            Platforms
          </h2>
          <div class="relative h-[220px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20"
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                border: `1px solid var(--console-home-carousel-button-border)`,
                color: 'var(--console-home-carousel-button-text)',
              }"
              @click="navigationFunctions.systems.prev"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20"
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                border: `1px solid var(--console-home-carousel-button-border)`,
                color: 'var(--console-home-carousel-button-text)',
              }"
              @click="navigationFunctions.systems.next"
            >
              ▶
            </button>
            <div
              ref="platforms-ref"
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
                    navigationMode === 'systems' && i === platformIndex
                  "
                  @click="goPlatform(p.id)"
                  @focus="platformIndex = i"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="recentRoms.length > 0"
          ref="recent-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            Recently Played
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20"
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                border: `1px solid var(--console-home-carousel-button-border)`,
                color: 'var(--console-home-carousel-button-text)',
              }"
              @click="navigationFunctions.recent.prev"
            >
              ◀
            </button>
            <button
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20"
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                border: `1px solid var(--console-home-carousel-button-border)`,
                color: 'var(--console-home-carousel-button-text)',
              }"
              @click="navigationFunctions.recent.next"
            >
              ▶
            </button>
            <div
              ref="recent-ref"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <GameCard
                  v-for="(g, i) in recentRoms"
                  :key="`${g.platform_id}-${g.id}`"
                  :rom="g"
                  :index="i"
                  :is-recent="true"
                  :selected="navigationMode === 'recent' && i === recentIndex"
                  :loaded="true"
                  @click="goGame(g)"
                  @focus="recentIndex = i"
                  @select="handleItemSelected"
                  @deselect="handleItemDeselected"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="collections.length > 0"
          ref="collections-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            Collections
          </h2>
          <div class="relative h-[400px]">
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.collections.prev"
            >
              ◀
            </button>
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.collections.next"
            >
              ▶
            </button>
            <div
              ref="collections-ref"
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
                  @select="handleItemSelected"
                  @deselect="handleItemDeselected"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="smartCollections.length > 0"
          ref="smart-collections-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            Smart Collections
          </h2>
          <div class="relative h-[400px]">
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.smartCollections.prev"
            >
              ◀
            </button>
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.smartCollections.next"
            >
              ▶
            </button>
            <div
              ref="smart-collections-ref"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <CollectionCard
                  v-for="(c, i) in smartCollections"
                  :key="`smart-collection-${c.id}`"
                  :collection="c"
                  :index="i"
                  :selected="
                    navigationMode === 'smartCollections' &&
                    i === smartCollectionsIndex
                  "
                  :loaded="true"
                  @click="goSmartCollection(c.id)"
                  @focus="smartCollectionsIndex = i"
                  @select="handleItemSelected"
                  @deselect="handleItemDeselected"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="virtualCollections.length > 0"
          ref="virtual-collections-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            Virtual Collections
          </h2>
          <div class="relative h-[400px]">
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.virtualCollections.prev"
            >
              ◀
            </button>
            <button
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                borderColor: 'var(--console-home-carousel-button-border)',
                color: 'var(--console-home-carousel-button-text)',
              }"
              class="absolute top-1/2 -translate-y-1/2 right-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20 border"
              @click="navigationFunctions.virtualCollections.next"
            >
              ▶
            </button>
            <div
              ref="virtual-collections-ref"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <CollectionCard
                  v-for="(c, i) in virtualCollections"
                  :key="`virtual-collection-${c.id}`"
                  :collection="c"
                  :index="i"
                  :selected="
                    navigationMode === 'virtualCollections' &&
                    i === virtualCollectionsIndex
                  "
                  :loaded="true"
                  @click="goVirtualCollection(c.id)"
                  @focus="virtualCollectionsIndex = i"
                  @select="handleItemSelected"
                  @deselect="handleItemDeselected"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="fixed top-4 right-4 z-20 flex gap-2">
        <button
          class="w-12 h-12 rounded-md cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:-translate-y-0.5 hover:shadow-lg"
          :style="{
            backgroundColor: 'var(--console-home-control-button-bg)',
            border: `1px solid var(--console-home-control-button-border)`,
            color: 'var(--console-home-control-button-text)',
          }"
          :class="{
            'border-[var(--console-home-control-button-focus-border)] bg-[var(--console-home-control-button-focus-border)]/15 shadow-[0_0_0_2px_var(--console-home-control-button-focus-border),_0_0_18px_-4px_var(--console-home-control-button-focus-border)] -translate-y-0.5':
              navigationMode === 'controls' && controlIndex === 0,
          }"
          title="Exit Console Mode (F1)"
          @click="exitConsoleMode"
        >
          ⏻
        </button>
        <button
          class="w-12 h-12 rounded-md cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:-translate-y-0.5 hover:shadow-lg"
          :style="{
            backgroundColor: 'var(--console-home-control-button-bg)',
            border: `1px solid var(--console-home-control-button-border)`,
            color: 'var(--console-home-control-button-text)',
          }"
          :class="{
            'border-[var(--console-home-control-button-focus-border)] bg-[var(--console-home-control-button-focus-border)]/15 shadow-[0_0_0_2px_var(--console-home-control-button-focus-border),_0_0_18px_-4px_var(--console-home-control-button-focus-border)] -translate-y-0.5':
              navigationMode === 'controls' && controlIndex === 1,
          }"
          title="Fullscreen (F11)"
          @click="toggleFullscreen"
        >
          ⛶
        </button>
        <button
          class="w-12 h-12 rounded-md cursor-pointer flex items-center justify-center text-xl transition-all backdrop-blur hover:-translate-y-0.5 hover:shadow-lg"
          :style="{
            backgroundColor: 'var(--console-home-control-button-bg)',
            border: `1px solid var(--console-home-control-button-border)`,
            color: 'var(--console-home-control-button-text)',
          }"
          :class="{
            'border-[var(--console-home-control-button-focus-border)] bg-[var(--console-home-control-button-focus-border)]/15 shadow-[0_0_0_2px_var(--console-home-control-button-focus-border),_0_0_18px_-4px_var(--console-home-control-button-focus-border)] -translate-y-0.5':
              navigationMode === 'controls' && controlIndex === 2,
          }"
          title="Settings"
          @click="showSettings = true"
        >
          ⚙
        </button>
      </div>

      <NavigationHint
        :show-back="false"
        :show-toggle-favorite="navigationMode === 'recent'"
      />
    </div>
    <SettingsModal v-model="showSettings" />
  </div>
</template>

<style scoped>
button:focus {
  outline: none;
}
</style>
