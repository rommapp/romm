<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import romApi from "@/services/api/rom";
import collectionApi from "@/services/api/collection";
import GameCard from "@/console/components/GameCard.vue";
import NavigationHint from "@/console/components/NavigationHint.vue";
import BackButton from "@/console/components/BackButton.vue";
import type { SimpleRomSchema } from "@/__generated__/models/SimpleRomSchema";
import type { CollectionSchema } from "@/__generated__/models/CollectionSchema";
import { useInputScope } from "@/console/composables/useInputScope";
import type { InputAction } from "@/console/input/actions";
import { useSpatialNav } from "@/console/composables/useSpatialNav";
import { useRovingDom } from "@/console/composables/useRovingDom";
import { gamesListElementRegistry } from "@/console/composables/useElementRegistry";
import consoleStore from "@/stores/console";
import useFavoriteToggle from "@/composables/useFavoriteToggle";
import type { SimpleRom } from "@/stores/roms";
import { ROUTES } from "@/plugins/router";

const route = useRoute();
const router = useRouter();
const storeConsole = consoleStore();
const { toggleFavorite: toggleFavoriteComposable } = useFavoriteToggle();

const isCollectionRoute = route.name === ROUTES.CONSOLE_COLLECTION;
const platformId = isCollectionRoute ? null : Number(route.params.id);
const collectionId = isCollectionRoute ? Number(route.params.id) : null;

const roms = ref<SimpleRomSchema[]>([]);
const collection = ref<CollectionSchema | null>(null);
const loading = ref(true);
const error = ref("");
const selectedIndex = ref(0);
const loadedMap = ref<Record<number, boolean>>({});
const inAlphabet = ref(false);
const alphaIndex = ref(0);
const gridRef = ref<HTMLDivElement>();

// Initialize selection from store
if (platformId != null) {
  selectedIndex.value = storeConsole.getPlatformGameIndex(platformId);
}
if (collectionId != null) {
  selectedIndex.value = storeConsole.getCollectionGameIndex(collectionId);
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
  }
  if (collectionId != null) {
    storeConsole.setCollectionGameIndex(collectionId, selectedIndex.value);
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
      if (rom) {
        // Cast SimpleRomSchema (generated) to store SimpleRom (alias) – shapes align
        toggleFavoriteComposable(rom as unknown as SimpleRom);
      }
      return true;
    }
    default:
      return false;
  }
}

function mouseSelect(i: number) {
  selectedIndex.value = i;
}

function selectAndOpen(i: number, rom: SimpleRomSchema) {
  selectedIndex.value = i;
  // Don't navigate if we're in alphabet mode
  if (inAlphabet.value) {
    return;
  }
  persistIndex();
  const query: Record<string, number> = {};
  if (platformId != null) query.id = platformId;
  if (isCollectionRoute) query.collection = collectionId!;
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
      <div v-if="loading" class="text-center text-fgDim mt-8">
        Loading games…
      </div>
      <div v-else-if="error" class="text-center text-red-400 mt-8">
        {{ error }}
      </div>
      <div v-else>
        <div v-if="roms.length === 0" class="text-center text-fgDim p-4">
          No games found.
        </div>
        <div
          ref="gridRef"
          class="grid grid-cols-[repeat(auto-fill,minmax(250px,250px))] justify-center my-12 gap-5 px-13 md:px-16 lg:px-20 xl:px-28 py-8 relative z-10 w-full box-border overflow-x-hidden"
          @wheel.prevent
        >
          <game-card
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
          />
        </div>
      </div>
    </div>
    <div
      class="w-[40px] bg-black/30 backdrop-blur border-l border-white/10 fixed top-0 right-0 h-screen overflow-hidden z-30 flex-shrink-0"
      :class="{
        'bg-[rgba(248,180,0,0.75)] border-l-[rgba(248,180,0,0.75)]': inAlphabet,
      }"
    >
      <div class="flex flex-col h-screen pa-2 items-center justify-evenly">
        <button
          v-for="(L, i) in letters"
          :key="L"
          class="bg-white/5 border border-white/10 text-fgDim rounded w-7 h-7 text-[0.7rem] font-semibold flex items-center justify-center shrink-0 transition-all hover:text-fg0 hover:border-white/30 hover:bg-white/10"
          :class="{
            'bg-[var(--accent-2)] border-[var(--accent)] text-white shadow-[0_0_0_2px_rgba(248,180,0,1)]':
              inAlphabet && i === alphaIndex,
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
