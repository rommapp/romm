<script setup lang="ts">
import { storeToRefs } from "pinia";
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  nextTick,
  useTemplateRef,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import useFavoriteToggle from "@/composables/useFavoriteToggle";
import BackButton from "@/console/components/BackButton.vue";
import GameCard from "@/console/components/GameCard.vue";
import NavigationHint from "@/console/components/NavigationHint.vue";
import useBackgroundArt from "@/console/composables/useBackgroundArt";
import { gamesListElementRegistry } from "@/console/composables/useElementRegistry";
import { useInputScope } from "@/console/composables/useInputScope";
import { useRovingDom } from "@/console/composables/useRovingDom";
import { useSpatialNav } from "@/console/composables/useSpatialNav";
import type { InputAction } from "@/console/input/actions";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeConsole from "@/stores/console";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";

const route = useRoute();
const router = useRouter();
const consoleStore = storeConsole();
const galleryFilterStore = storeGalleryFilter();
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const collectionsStore = storeCollections();
const { allCollections, smartCollections, virtualCollections } =
  storeToRefs(collectionsStore);
const romsStore = storeRoms();
const {
  filteredRoms,
  fetchingRoms,
  currentPlatform,
  currentCollection,
  currentSmartCollection,
  currentVirtualCollection,
} = storeToRefs(romsStore);
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();
const { setSelectedBackgroundArt, clearSelectedBackgroundArt } =
  useBackgroundArt();

const isPlatformRoute = route.name === ROUTES.CONSOLE_PLATFORM;
const isCollectionRoute = route.name === ROUTES.CONSOLE_COLLECTION;
const isSmartCollectionRoute = route.name === ROUTES.CONSOLE_SMART_COLLECTION;
const isVirtualCollectionRoute =
  route.name === ROUTES.CONSOLE_VIRTUAL_COLLECTION;

const selectedIndex = ref(0);
const loadedMap = ref<Record<number, boolean>>({});
const inAlphabet = ref(false);
const alphaIndex = ref(0);
const gridRef = useTemplateRef<HTMLDivElement>("game-grid-ref");

// Generate alphabet letters dynamically based on available games
const letters = computed(() => {
  const letterSet = new Set<string>();

  filteredRoms.value.forEach(({ name }) => {
    if (!name) return;

    const normalized = normalizeTitle(name);
    const firstChar = normalized.charAt(0).toUpperCase();

    if (/[A-Z]/.test(firstChar)) {
      letterSet.add(firstChar);
    } else if (/[0-9]/.test(firstChar)) {
      letterSet.add("#");
    }
  });

  const result = Array.from(letterSet).sort();
  // Move # to the beginning if it exists
  const hashIndex = result.indexOf("#");
  if (hashIndex > -1) {
    result.splice(hashIndex, 1);
    result.unshift("#");
  }

  return result;
});

function persistIndex() {
  if (currentPlatform.value != null) {
    consoleStore.setPlatformGameIndex(
      currentPlatform.value.id,
      selectedIndex.value,
    );
  } else if (currentCollection.value != null) {
    consoleStore.setCollectionGameIndex(
      currentCollection.value.id,
      selectedIndex.value,
    );
  } else if (currentSmartCollection.value != null) {
    consoleStore.setSmartCollectionGameIndex(
      currentSmartCollection.value.id,
      selectedIndex.value,
    );
  } else if (currentVirtualCollection.value != null) {
    consoleStore.setVirtualCollectionGameIndex(
      currentVirtualCollection.value.id,
      selectedIndex.value,
    );
  }
}

function navigateBack() {
  persistIndex();
  router.push({ name: ROUTES.CONSOLE_HOME });
}

const headerTitle = computed(() => {
  if (isCollectionRoute) {
    return currentCollection.value?.name || "Collection";
  }
  if (isSmartCollectionRoute) {
    return currentSmartCollection.value?.name || "Smart Collection";
  }
  if (isVirtualCollectionRoute) {
    return currentVirtualCollection.value?.name || "Virtual Collection";
  }

  return (
    currentPlatform.value?.display_name ||
    currentPlatform.value?.slug.toUpperCase()
  );
});

function getCols(): number {
  if (!gridRef.value) return 4;

  try {
    const style = window.getComputedStyle(gridRef.value);
    return Math.max(1, style.gridTemplateColumns.split(" ").length);
  } catch {
    return 4;
  }
}

// Selected element access
const cardElementAt = (i: number) => gamesListElementRegistry.getElement(i);
useRovingDom(selectedIndex, (i) => cardElementAt(i), {
  block: "center",
  inline: "nearest",
});

const { subscribe } = useInputScope();
const {
  moveLeft,
  moveRight,
  moveUp,
  moveDown: moveDownBasic,
} = useSpatialNav(selectedIndex, getCols, () => filteredRoms.value.length);

function handleAction(action: InputAction): boolean {
  if (!filteredRoms.value.length) return false;
  if (inAlphabet.value) {
    if (action === "moveLeft") {
      inAlphabet.value = false;
      return true;
    }
    if (action === "moveUp") {
      alphaIndex.value = Math.max(0, alphaIndex.value - 1);
      return true;
    }
    if (action === "moveDown") {
      alphaIndex.value = Math.min(
        Array.from(letters.value).length - 1,
        alphaIndex.value + 1,
      );
      return true;
    }
    if (action === "confirm") {
      const L = Array.from(letters.value)[alphaIndex.value];
      const idx = filteredRoms.value.findIndex((r) => {
        const normalized = normalizeTitle(r.name || "");
        if (L === "#") {
          return /^[0-9]/.test(normalized);
        }
        return normalized.startsWith(L);
      });
      if (idx >= 0) {
        selectedIndex.value = idx;
        // Stay in alphabet mode, just highlight the game
        nextTick(() => {
          cardElementAt(selectedIndex.value)?.scrollIntoView({
            block: "center",
            inline: "nearest",
            behavior: "smooth" as ScrollBehavior,
          });
        });
      }
      return true;
    }
    if (action === "back") {
      inAlphabet.value = false;
      return true;
    }
    return true;
  }
  switch (action) {
    case "moveRight": {
      const before = selectedIndex.value;
      moveRight();
      if (selectedIndex.value === before) {
        inAlphabet.value = true;
        alphaIndex.value = 0;
      }
      return true;
    }
    case "moveLeft":
      moveLeft();
      return true;
    case "moveUp":
      moveUp();
      return true;
    case "moveDown": {
      const before = selectedIndex.value;
      moveDownBasic();
      if (selectedIndex.value === before) {
        const cols = getCols();
        const count = filteredRoms.value.length;
        const totalRows = Math.ceil(count / cols);
        const currentRow = Math.floor(before / cols);
        if (totalRows > currentRow + 1) {
          selectedIndex.value = count - 1;
        }
      }
      return true;
    }
    case "back":
      navigateBack();
      return true;
    case "confirm": {
      selectAndOpen(
        selectedIndex.value,
        filteredRoms.value[selectedIndex.value],
      );
      return true;
    }
    case "toggleFavorite": {
      const rom = filteredRoms.value[selectedIndex.value];
      if (rom) toggleFavoriteComposable(rom);
      return true;
    }
    default:
      return false;
  }
}

function mouseSelect(i: number) {
  selectedIndex.value = i;
}

function selectAndOpen(i: number, rom: SimpleRom) {
  selectedIndex.value = i;
  // Don't navigate if we're in alphabet mode
  if (inAlphabet.value) return;

  persistIndex();

  const query: Record<string, number | string> = {};
  if (isPlatformRoute && currentPlatform.value != null)
    query.id = currentPlatform.value.id;
  if (isCollectionRoute && currentCollection.value != null)
    query.collection = currentCollection.value.id;
  if (isSmartCollectionRoute && currentSmartCollection.value != null)
    query.smartCollection = currentSmartCollection.value.id;
  if (isVirtualCollectionRoute && currentVirtualCollection.value != null)
    query.virtualCollection = currentVirtualCollection.value.id;

  router.push({
    name: ROUTES.CONSOLE_ROM,
    params: { rom: rom.id },
    query: Object.keys(query).length ? query : undefined,
  });
}

function jumpToLetter(L: string) {
  const idx = filteredRoms.value.findIndex((r) => {
    const normalized = normalizeTitle(r.name || "");
    if (L === "#") {
      return /^[0-9]/.test(normalized);
    }
    return normalized.startsWith(L);
  });

  if (idx >= 0) {
    selectedIndex.value = idx;
    inAlphabet.value = false;
  }
}

function normalizeTitle(name: string) {
  return name.toUpperCase().replace(/^(THE|A|AN)\s+/, "");
}

let off: (() => void) | null = null;

function resetGallery() {
  romsStore.reset();
  galleryFilterStore.resetFilters();
  galleryFilterStore.activeFilterDrawer = false;
}

async function fetchRoms() {
  romsStore.setLimit(500);
  romsStore.setOrderBy("name");
  romsStore.setOrderDir("asc");
  romsStore.resetPagination();

  const fetchedRoms = await romsStore.fetchRoms({
    galleryFilter: galleryFilterStore,
    concat: false,
  });

  if (selectedIndex.value >= fetchedRoms.length) selectedIndex.value = 0;
  await nextTick();

  cardElementAt(selectedIndex.value)?.scrollIntoView({
    block: "center",
    inline: "nearest",
    behavior: "instant" as ScrollBehavior,
  });
}

onMounted(async () => {
  const routePlatformId = isPlatformRoute ? Number(route.params.id) : null;
  const routeCollectionId = isCollectionRoute ? Number(route.params.id) : null;
  const routeSmartCollectionId = isSmartCollectionRoute
    ? Number(route.params.id)
    : null;
  const routeVirtualCollectionId = isVirtualCollectionRoute
    ? String(route.params.id)
    : null;

  watch(
    () => allPlatforms.value,
    async (platforms) => {
      if (platforms.length > 0) {
        const platform = platforms.find(
          (platform) => platform.id === routePlatformId,
        );

        if (!platform) return;
        // Check if the current platform is different or no ROMs have been loaded
        if (
          currentPlatform.value?.id !== routePlatformId ||
          filteredRoms.value.length === 0
        ) {
          resetGallery();
          romsStore.setCurrentPlatform(platform);
          selectedIndex.value = consoleStore.getPlatformGameIndex(platform.id);
          document.title = platform.display_name;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => allCollections.value,
    async (collections) => {
      if (collections.length > 0) {
        const collection = collections.find(
          (collection) => collection.id === routeCollectionId,
        );

        if (!collection) return;
        // Check if the current collection is different or no ROMs have been loaded
        if (
          currentCollection.value?.id !== routeCollectionId ||
          filteredRoms.value.length === 0
        ) {
          resetGallery();
          romsStore.setCurrentCollection(collection);
          selectedIndex.value = consoleStore.getCollectionGameIndex(
            collection.id,
          );
          document.title = collection.name;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => smartCollections.value,
    async (smartCollections) => {
      if (smartCollections.length > 0) {
        const smartCollection = smartCollections.find(
          (smartCollection) => smartCollection.id === routeSmartCollectionId,
        );

        if (!smartCollection) return;
        // Check if the current smartCollection is different or no ROMs have been loaded
        if (
          currentSmartCollection.value?.id !== routeSmartCollectionId ||
          filteredRoms.value.length === 0
        ) {
          resetGallery();
          romsStore.setCurrentSmartCollection(smartCollection);
          selectedIndex.value = consoleStore.getSmartCollectionGameIndex(
            smartCollection.id,
          );
          document.title = smartCollection.name;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => virtualCollections.value,
    async (virtualCollections) => {
      if (virtualCollections.length > 0) {
        const virtualCollection = virtualCollections.find(
          (virtualCollection) =>
            virtualCollection.id === routeVirtualCollectionId,
        );

        if (!virtualCollection) return;
        // Check if the current virtualCollection is different or no ROMs have been loaded
        if (
          currentVirtualCollection.value?.id !== routeVirtualCollectionId ||
          filteredRoms.value.length === 0
        ) {
          resetGallery();
          romsStore.setCurrentVirtualCollection(virtualCollection);
          selectedIndex.value = consoleStore.getVirtualCollectionGameIndex(
            virtualCollection.id,
          );
          document.title = virtualCollection.name;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  off = subscribe(handleAction);
});

onUnmounted(() => {
  off?.();
  off = null;
  persistIndex();
});

function markLoaded(id: number) {
  loadedMap.value[id] = true;
}

function handleItemSelected(coverUrl: string) {
  setSelectedBackgroundArt(coverUrl);
}

function handleItemDeselected() {
  clearSelectedBackgroundArt();
}
</script>

<template>
  <div
    class="relative min-h-screen overflow-y-auto overflow-x-hidden max-w-[100vw] flex"
    @wheel.prevent
  >
    <BackButton :text="headerTitle" :on-back="navigateBack" />
    <div
      class="relative flex-1 min-w-0 pr-[40px]"
      :style="{ width: 'calc(100vw - 40px)' }"
    >
      <div
        v-if="fetchingRoms"
        class="text-center mt-8"
        :style="{ color: 'var(--console-loading-text)' }"
      >
        Loading games…
      </div>
      <div v-else>
        <div
          v-if="filteredRoms.length === 0"
          class="text-center text-fgDim p-4"
        >
          No games found.
        </div>
        <div
          ref="game-grid-ref"
          class="grid grid-cols-[repeat(auto-fill,minmax(250px,250px))] justify-center my-12 gap-5 px-13 md:px-16 lg:px-20 xl:px-28 py-8 relative z-10 w-full box-border overflow-x-hidden"
          @wheel.prevent
        >
          <GameCard
            v-for="(rom, i) in filteredRoms"
            :key="rom.id"
            :rom="rom"
            :index="i"
            :selected="!inAlphabet && i === selectedIndex"
            :loaded="!!loadedMap[rom.id]"
            registry="gamesList"
            @click="selectAndOpen(i, rom)"
            @focus="mouseSelect(i)"
            @loaded="markLoaded(rom.id)"
            @select="handleItemSelected"
            @deselect="handleItemDeselected"
          />
        </div>
      </div>
    </div>
    <div
      class="w-[40px] backdrop-blur fixed top-0 right-0 h-screen overflow-hidden z-30 flex-shrink-0"
      :style="{
        backgroundColor: 'var(--console-gameslist-scrollbar-bg)',
      }"
    >
      <div class="flex flex-col h-screen pa-2 items-center justify-evenly">
        <button
          v-for="(L, i) in letters"
          :key="L"
          class="rounded w-7 h-7 text-[0.7rem] font-semibold flex items-center justify-center shrink-0 transition-all border"
          :style="{
            backgroundColor:
              inAlphabet && i === alphaIndex
                ? 'var(--console-gameslist-alphabet-active-bg)'
                : 'var(--console-gameslist-alphabet-bg)',
            borderColor: 'var(--console-gameslist-alphabet-border)',
            color:
              inAlphabet && i === alphaIndex
                ? 'var(--console-gameslist-alphabet-active-text)'
                : 'var(--console-gameslist-alphabet-text)',
            boxShadow:
              inAlphabet && i === alphaIndex
                ? '0 0 0 2px var(--console-gameslist-alphabet-active-bg)'
                : 'none',
          }"
          @click="jumpToLetter(L)"
        >
          {{ L }}
        </button>
      </div>
    </div>
    <NavigationHint :show-toggle-favorite="true" />
  </div>
</template>

<style scoped>
button:focus {
  outline: none;
}
</style>
