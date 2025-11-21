<script setup lang="ts">
import { storeToRefs } from "pinia";
import {
  onMounted,
  onUnmounted,
  ref,
  nextTick,
  watch,
  useTemplateRef,
  onBeforeMount,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
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
  continuePlayingElementRegistry,
  collectionElementRegistry,
  smartCollectionElementRegistry,
  virtualCollectionElementRegistry,
} from "@/console/composables/useElementRegistry";
import { useInputScope } from "@/console/composables/useInputScope";
import { useRovingDom } from "@/console/composables/useRovingDom";
import { useSpatialNav } from "@/console/composables/useSpatialNav";
import type { InputAction } from "@/console/input/actions";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeConsole from "@/stores/console";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { SimpleRom } from "@/stores/roms";

const { t } = useI18n();
const router = useRouter();
const platformsStore = storePlatforms();
const { allPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);
const collectionsStore = storeCollections();
const { allCollections, smartCollections, virtualCollections } =
  storeToRefs(collectionsStore);
const romsStore = storeRoms();
const { continuePlayingRoms } = storeToRefs(romsStore);
const consoleStore = storeConsole();
const {
  navigationMode,
  platformIndex,
  continuePlayingIndex,
  collectionsIndex,
  smartCollectionsIndex,
  virtualCollectionsIndex,
  controlIndex,
} = storeToRefs(consoleStore);
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();
const { setSelectedBackgroundArt, clearSelectedBackgroundArt } =
  useBackgroundArt();
const { subscribe } = useInputScope();

const errorMessage = ref("");
const showSettings = ref(false);

// Navigation indices
const scrollContainerRef = useTemplateRef<HTMLDivElement>(
  "scroll-container-ref",
);
const platformsRef = useTemplateRef<HTMLDivElement>("platforms-ref");
const continuePlayingRef = useTemplateRef<HTMLDivElement>(
  "continue-playing-ref",
);
const collectionsRef = useTemplateRef<HTMLDivElement>("collections-ref");
const smartCollectionsRef = useTemplateRef<HTMLDivElement>(
  "smart-collections-ref",
);
const virtualCollectionsRef = useTemplateRef<HTMLDivElement>(
  "virtual-collections-ref",
);
const continuePlayingSectionRef = useTemplateRef<HTMLElement>(
  "continue-playing-section-ref",
);
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
const continuePlayingElementAt = (i: number) =>
  continuePlayingElementRegistry.getElement(i);
const collectionElementAt = (i: number) =>
  collectionElementRegistry.getElement(i);
const smartCollectionElementAt = (i: number) =>
  smartCollectionElementRegistry.getElement(i);
const virtualCollectionElementAt = (i: number) =>
  virtualCollectionElementRegistry.getElement(i);

// Spatial navigation
const { moveLeft: moveSystemLeft, moveRight: moveSystemRight } = useSpatialNav(
  platformIndex,
  () => allPlatforms.value.length || 1,
  () => allPlatforms.value.length,
);
const {
  moveLeft: moveContinuePlayingLeft,
  moveRight: moveContinuePlayingRight,
} = useSpatialNav(
  continuePlayingIndex,
  () => continuePlayingRoms.value.length || 1,
  () => continuePlayingRoms.value.length,
);
const { moveLeft: moveCollectionLeft, moveRight: moveCollectionRight } =
  useSpatialNav(
    collectionsIndex,
    () => allCollections.value.length || 1,
    () => allCollections.value.length,
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
useRovingDom(continuePlayingIndex, continuePlayingElementAt, {
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

watch(continuePlayingIndex, (newIdx) => {
  if (!isVerticalScrolling) {
    const el = continuePlayingElementAt(newIdx);
    if (el && continuePlayingRef.value) {
      centerInCarousel(continuePlayingRef.value, el, "smooth");
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
        platformIndex.value = Math.max(0, allPlatforms.value.length - 1);
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
      if (!allPlatforms.value[platformIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_PLATFORM,
        params: { id: allPlatforms.value[platformIndex.value].id },
      });
      return true;
    },
  },
  continuePlaying: {
    prev: () => {
      const before = continuePlayingIndex.value;
      moveContinuePlayingLeft();
      if (continuePlayingIndex.value === before) {
        continuePlayingIndex.value = Math.max(
          0,
          continuePlayingRoms.value.length - 1,
        );
      }
    },
    next: () => {
      const before = continuePlayingIndex.value;
      moveContinuePlayingRight();
      if (continuePlayingIndex.value === before) {
        continuePlayingIndex.value = 0;
      }
    },
    confirm: () => {
      if (!continuePlayingRoms.value[continuePlayingIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_ROM,
        params: {
          rom: continuePlayingRoms.value[continuePlayingIndex.value].id,
        },
        query: {
          id: continuePlayingRoms.value[continuePlayingIndex.value].platform_id,
        },
      });
      return true;
    },
  },
  collections: {
    prev: () => {
      const before = collectionsIndex.value;
      moveCollectionLeft();
      if (collectionsIndex.value === before) {
        collectionsIndex.value = Math.max(0, allCollections.value.length - 1);
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
      if (!allCollections.value[collectionsIndex.value]) return false;
      router.push({
        name: ROUTES.CONSOLE_COLLECTION,
        params: { id: allCollections.value[collectionsIndex.value].id },
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

let isVerticalScrolling = false;

function scrollToCurrentRow() {
  isVerticalScrolling = true;

  const behavior: ScrollBehavior = "smooth";
  switch (navigationMode.value) {
    case "systems":
      scrollContainerRef.value?.scrollTo({ top: 0, behavior });
      break;
    case "continuePlaying":
      continuePlayingSectionRef.value?.scrollIntoView({
        behavior,
        block: "start",
      });
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

  setTimeout(() => {
    isVerticalScrolling = false;
  }, 400);
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
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else {
    document.documentElement.requestFullscreen?.();
  }
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
      if (currentMode === "continuePlaying") {
        navigationMode.value = "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "collections") {
        navigationMode.value =
          continuePlayingRoms.value.length > 0 ? "continuePlaying" : "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "smartCollections") {
        navigationMode.value =
          allCollections.value.length > 0
            ? "collections"
            : continuePlayingRoms.value.length > 0
              ? "continuePlaying"
              : "systems";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "virtualCollections") {
        navigationMode.value =
          smartCollections.value.length > 0
            ? "smartCollections"
            : allCollections.value.length > 0
              ? "collections"
              : continuePlayingRoms.value.length > 0
                ? "continuePlaying"
                : "systems";
        scrollToCurrentRow();
        return true;
      }
      return false;

    case "moveDown":
      if (currentMode === "systems") {
        navigationMode.value =
          continuePlayingRoms.value.length > 0
            ? "continuePlaying"
            : allCollections.value.length > 0
              ? "collections"
              : smartCollections.value.length > 0
                ? "smartCollections"
                : virtualCollections.value.length > 0
                  ? "virtualCollections"
                  : "controls";
        scrollToCurrentRow();
        return true;
      }
      if (currentMode === "continuePlaying") {
        navigationMode.value =
          allCollections.value.length > 0
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
      if (
        currentMode === "continuePlaying" &&
        continuePlayingRoms.value[continuePlayingIndex.value]
      ) {
        toggleFavoriteComposable(
          continuePlayingRoms.value[continuePlayingIndex.value],
        );
        return true;
      }
      return false;

    default:
      return false;
  }
}

onBeforeMount(async () => {
  await romsStore.fetchContinuePlayingRoms();
});

onMounted(async () => {
  // Restore indices within bounds
  if (platformIndex.value >= allPlatforms.value.length) platformIndex.value = 0;
  if (continuePlayingIndex.value >= continuePlayingRoms.value.length)
    continuePlayingIndex.value = 0;
  if (collectionsIndex.value >= allCollections.value.length)
    collectionsIndex.value = 0;
  if (smartCollectionsIndex.value >= smartCollections.value.length)
    smartCollectionsIndex.value = 0;
  if (virtualCollectionsIndex.value >= virtualCollections.value.length)
    virtualCollectionsIndex.value = 0;

  await nextTick();
  scrollToCurrentRow();

  // Center carousels
  centerInCarousel(platformsRef.value, systemElementAt(platformIndex.value));
  centerInCarousel(
    continuePlayingRef.value,
    continuePlayingElementAt(continuePlayingIndex.value),
  );
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
  consoleStore.setHomeState({
    platformIndex: platformIndex.value,
    continuePlayingIndex: continuePlayingIndex.value,
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
          {{ t("console.console") }}
        </div>
      </div>

      <div
        v-if="fetchingPlatforms"
        class="text-center mt-16"
        :style="{ color: 'var(--console-loading-text)' }"
      >
        {{ t("console.loading-platforms") }}
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
            {{ t("console.platforms") }}
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
                  v-for="(p, i) in allPlatforms"
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
          v-if="continuePlayingRoms.length > 0"
          ref="continue-playing-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            {{ t("console.recently-played") }}
          </h2>
          <div class="relative h-[400px]">
            <button
              class="absolute top-1/2 -translate-y-1/2 left-2 w-10 h-10 rounded-full flex items-center justify-center cursor-pointer transition-all backdrop-blur z-20"
              :style="{
                backgroundColor: 'var(--console-home-carousel-button-bg)',
                border: `1px solid var(--console-home-carousel-button-border)`,
                color: 'var(--console-home-carousel-button-text)',
              }"
              @click="navigationFunctions.continuePlaying.prev"
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
              @click="navigationFunctions.continuePlaying.next"
            >
              ▶
            </button>
            <div
              ref="continue-playing-ref"
              class="w-full h-full overflow-x-auto overflow-y-hidden no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none]"
              @wheel.prevent
            >
              <div class="flex items-center gap-4 h-full px-12 min-w-max">
                <GameCard
                  v-for="(g, i) in continuePlayingRoms"
                  :key="`${g.platform_id}-${g.id}`"
                  :rom="g"
                  :index="i"
                  :continue-playing="true"
                  :selected="
                    navigationMode === 'continuePlaying' &&
                    i === continuePlayingIndex
                  "
                  :loaded="true"
                  @click="goGame(g)"
                  @focus="continuePlayingIndex = i"
                  @select="handleItemSelected"
                  @deselect="handleItemDeselected"
                />
              </div>
            </div>
          </div>
        </section>

        <section
          v-if="allCollections.length > 0"
          ref="collections-section-ref"
          class="pb-8"
        >
          <h2
            class="text-xl font-bold text-fg0 mb-3 drop-shadow pl-8 pr-8"
            :style="{ color: 'var(--console-home-category-text)' }"
          >
            {{ t("console.collections") }}
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
                  v-for="(c, i) in allCollections"
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
            {{ t("console.smart-collections") }}
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
            {{ t("console.virtual-collections") }}
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
          :title="t('console.exit-console-mode') + ' (F1)'"
          @click="exitConsoleMode"
        >
          <v-icon size="small">mdi-power</v-icon>
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
          :title="t('console.fullscreen') + ' (F11)'"
          @click="toggleFullscreen"
        >
          <v-icon size="small">mdi-fullscreen</v-icon>
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
          :title="t('console.settings')"
          @click="showSettings = true"
        >
          <v-icon size="small">mdi-cog</v-icon>
        </button>
      </div>

      <NavigationHint
        :show-back="false"
        :show-toggle-favorite="navigationMode === 'continuePlaying'"
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
