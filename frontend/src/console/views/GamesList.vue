<script setup lang="ts">
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  nextTick,
  useTemplateRef,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import type { CollectionSchema } from "@/__generated__/models/CollectionSchema";
import type { SmartCollectionSchema } from "@/__generated__/models/SmartCollectionSchema";
import type { VirtualCollectionSchema } from "@/__generated__/models/VirtualCollectionSchema";
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
import collectionApi from "@/services/api/collection";
import romApi from "@/services/api/rom";
import consoleStore from "@/stores/console";
import type { SimpleRom } from "@/stores/roms";

const route = useRoute();
const router = useRouter();
const storeConsole = consoleStore();
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();
const { setSelectedBackgroundArt, clearSelectedBackgroundArt } =
  useBackgroundArt();

const isCollectionRoute = route.name === ROUTES.CONSOLE_COLLECTION;
const isSmartCollectionRoute = route.name === ROUTES.CONSOLE_SMART_COLLECTION;
const isVirtualCollectionRoute =
  route.name === ROUTES.CONSOLE_VIRTUAL_COLLECTION;

const platformId =
  isCollectionRoute || isSmartCollectionRoute || isVirtualCollectionRoute
    ? null
    : Number(route.params.id);
const collectionId = isCollectionRoute ? Number(route.params.id) : null;
const smartCollectionId = isSmartCollectionRoute
  ? Number(route.params.id)
  : null;
const virtualCollectionId = isVirtualCollectionRoute
  ? String(route.params.id)
  : null;

const roms = ref<SimpleRom[]>([]);
const collection = ref<CollectionSchema | null>(null);
const smartCollection = ref<SmartCollectionSchema | null>(null);
const virtualCollection = ref<VirtualCollectionSchema | null>(null);
const loading = ref(true);
const error = ref("");
const selectedIndex = ref(0);
const loadedMap = ref<Record<number, boolean>>({});
const inAlphabet = ref(false);
const alphaIndex = ref(0);
const gridRef = useTemplateRef<HTMLDivElement>("game-grid-ref");

// Initialize selection from store
if (platformId != null) {
  selectedIndex.value = storeConsole.getPlatformGameIndex(platformId);
} else if (collectionId != null) {
  selectedIndex.value = storeConsole.getCollectionGameIndex(collectionId);
} else if (smartCollectionId != null) {
  selectedIndex.value = storeConsole.getCollectionGameIndex(smartCollectionId);
} else if (virtualCollectionId != null) {
  selectedIndex.value = storeConsole.getCollectionGameIndex(
    Number(virtualCollectionId),
  );
}

// Generate alphabet letters dynamically based on available games
const letters = computed(() => {
  const letterSet = new Set<string>();

  roms.value.forEach(({ name }) => {
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
  if (platformId != null) {
    storeConsole.setPlatformGameIndex(platformId, selectedIndex.value);
  } else if (collectionId != null) {
    storeConsole.setCollectionGameIndex(collectionId, selectedIndex.value);
  } else if (smartCollectionId != null) {
    storeConsole.setCollectionGameIndex(smartCollectionId, selectedIndex.value);
  } else if (virtualCollectionId != null) {
    storeConsole.setCollectionGameIndex(
      Number(virtualCollectionId),
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
    return collection.value?.name || "Collection";
  }
  if (isSmartCollectionRoute) {
    return smartCollection.value?.name || "Smart Collection";
  }
  if (isVirtualCollectionRoute) {
    return virtualCollection.value?.name || "Virtual Collection";
  }

  return (
    current.value?.platform_name ||
    current.value?.platform_slug?.toUpperCase() ||
    "Platform"
  );
});

const current = computed(
  () => roms.value[selectedIndex.value] || roms.value[0],
);

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
} = useSpatialNav(selectedIndex, getCols, () => roms.value.length);

function handleAction(action: InputAction): boolean {
  if (!roms.value.length) return false;
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
      const idx = roms.value.findIndex((r) => {
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
        const count = roms.value.length;
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
      selectAndOpen(selectedIndex.value, roms.value[selectedIndex.value]);
      return true;
    }
    case "toggleFavorite": {
      const rom = roms.value[selectedIndex.value];
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
  if (platformId != null) query.id = platformId;
  if (isCollectionRoute) query.collection = collectionId!;
  if (isSmartCollectionRoute) query.smartCollection = smartCollectionId!;
  if (isVirtualCollectionRoute) query.virtualCollection = virtualCollectionId!;

  router.push({
    name: ROUTES.CONSOLE_ROM,
    params: { rom: rom.id },
    query: Object.keys(query).length ? query : undefined,
  });
}

function jumpToLetter(L: string) {
  const idx = roms.value.findIndex((r) => {
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

onMounted(async () => {
  try {
    if (platformId != null) {
      const { data } = await romApi.getRoms({
        platformId: platformId,
        limit: 500,
        orderBy: "name",
        orderDir: "asc",
      });
      roms.value = data.items ?? [];
    } else if (collectionId != null) {
      const { data } = await romApi.getRoms({
        collectionId: collectionId,
        limit: 500,
        orderBy: "name",
        orderDir: "asc",
      });
      roms.value = data.items ?? [];
      const { data: col } = await collectionApi.getCollection(collectionId);
      collection.value = col ?? null;
    } else if (smartCollectionId != null) {
      const { data } = await romApi.getRoms({
        smartCollectionId: smartCollectionId,
        limit: 500,
        orderBy: "name",
        orderDir: "asc",
      });
      roms.value = data.items ?? [];
      const { data: smartCol } =
        await collectionApi.getSmartCollection(smartCollectionId);
      smartCollection.value = smartCol ?? null;
    } else if (virtualCollectionId != null) {
      const { data } = await romApi.getRoms({
        virtualCollectionId: virtualCollectionId,
        limit: 500,
        orderBy: "name",
        orderDir: "asc",
      });
      roms.value = data.items ?? [];
      const { data: virtualCol } =
        await collectionApi.getVirtualCollection(virtualCollectionId);
      virtualCollection.value = virtualCol ?? null;
    }
    for (const r of roms.value) {
      if (!r.url_cover && !r.path_cover_large && !r.path_cover_small) {
        loadedMap.value[r.id] = true;
      }
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Failed to load roms";
  } finally {
    loading.value = false;
  }

  if (selectedIndex.value >= roms.value.length) selectedIndex.value = 0;
  await nextTick();
  cardElementAt(selectedIndex.value)?.scrollIntoView({
    block: "center",
    inline: "nearest",
    behavior: "instant" as ScrollBehavior,
  });
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
        v-if="loading"
        class="text-center mt-8"
        :style="{ color: 'var(--console-loading-text)' }"
      >
        Loading games…
      </div>
      <div
        v-else-if="error"
        class="text-center mt-8"
        :style="{ color: 'var(--console-error-text)' }"
      >
        {{ error }}
      </div>
      <div v-else>
        <div v-if="roms.length === 0" class="text-center text-fgDim p-4">
          No games found.
        </div>
        <div
          ref="game-grid-ref"
          class="grid grid-cols-[repeat(auto-fill,minmax(250px,250px))] justify-center my-12 gap-5 px-13 md:px-16 lg:px-20 xl:px-28 py-8 relative z-10 w-full box-border overflow-x-hidden"
          @wheel.prevent
        >
          <GameCard
            v-for="(rom, i) in roms"
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
