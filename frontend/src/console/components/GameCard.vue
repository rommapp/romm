<script setup lang="ts">
import { computed, onMounted, useTemplateRef, watch } from "vue";
import {
  recentElementRegistry,
  gamesListElementRegistry,
} from "@/console/composables/useElementRegistry";
import storeCollections from "@/stores/collections";
import type { SimpleRom } from "@/stores/roms";

const props = defineProps<{
  rom: SimpleRom;
  index: number;
  selected?: boolean;
  loaded?: boolean;
  isRecent?: boolean;
  registry?: "recent" | "gamesList";
}>();
const coverSrc = computed(
  () =>
    props.rom.path_cover_large ||
    props.rom.path_cover_small ||
    props.rom.url_cover ||
    "",
);
const emit = defineEmits([
  "click",
  "mouseenter",
  "focus",
  "loaded",
  "select",
  "deselect",
]);
const gameCardRef = useTemplateRef<HTMLButtonElement>("game-card-ref");

// Check if this game is in the favorites collection
const collectionsStore = storeCollections();
const isFavorited = computed(() => {
  return collectionsStore.isFavorite(props.rom);
});

// Watch for selection changes and emit events
watch(
  () => props.selected,
  (isSelected) => {
    if (isSelected && coverSrc.value) {
      emit("select", props.rom);
    } else if (!isSelected) {
      emit("deselect");
    }
  },
  { immediate: true },
);

onMounted(() => {
  if (!gameCardRef.value) return;

  if (props.registry === "gamesList") {
    gamesListElementRegistry.registerElement(props.index, gameCardRef.value);
  } else {
    recentElementRegistry.registerElement(props.index, gameCardRef.value);
  }
});
</script>

<template>
  <button
    ref="game-card-ref"
    class="relative block border-2 border-white/10 rounded-md p-0 cursor-pointer overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)] transition-all duration-200"
    :class="{
      '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--console-game-card-focus-border),_0_0_16px_var(--console-game-card-focus-border)]':
        selected,
      'w-[250px] shrink-0': isRecent,
    }"
    @click="emit('click')"
    @focus="emit('focus')"
  >
    <div
      class="w-full h-[350px] relative overflow-hidden rounded"
      :style="{ background: 'var(--console-game-card-bg)' }"
    >
      <img
        v-if="coverSrc"
        class="w-full h-full object-cover"
        :src="coverSrc"
        :alt="rom.name || 'Game'"
        @load="emit('loaded')"
        @error="emit('loaded')"
      />
      <div
        v-else
        class="w-full h-full"
        :style="{ background: 'var(--console-game-card-bg)' }"
      />
      <!-- Selected highlight radial glow -->
      <div
        class="absolute inset-0 opacity-0 pointer-events-none"
        :style="{
          background:
            'radial-gradient(circle at center, var(--console-game-card-focus-border) 0%, transparent 70%)',
        }"
        :class="{ 'opacity-10': selected }"
      />
      <div
        v-if="!loaded"
        class="absolute inset-0 bg-gradient-to-r from-white/10 via-white/20 to-white/10 bg-[length:200%_100%] animate-[shimmer_1.2s_linear_infinite]"
      />

      <!-- Favorite star icon -->
      <div v-if="isFavorited" class="absolute top-2 right-2 z-20">
        <div class="bg-black/50 backdrop-blur-sm rounded-full">
          <v-icon size="27" style="color: var(--console-game-card-star)">
            mdi-star
          </v-icon>
        </div>
      </div>

      <div
        v-if="!coverSrc"
        class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-b from-transparent to-black/75 text-[var(--console-game-card-text)] text-sm leading-tight z-10"
      >
        <div class="font-medium truncate">
          {{ rom.name || "Untitled Game" }}
        </div>
        <div
          v-if="
            rom.metadatum.first_release_date || rom.metadatum.companies?.length
          "
          class="text-[var(--console-game-card-text)] text-xs opacity-90"
        >
          {{
            rom.metadatum.first_release_date
              ? new Date(rom.metadatum.first_release_date * 1000).getFullYear()
              : ""
          }}
          <template
            v-if="
              rom.metadatum.first_release_date &&
              rom.metadatum.companies?.length
            "
          >
            •
          </template>
          {{ rom.metadatum.companies?.[0] || "" }}
        </div>
      </div>
    </div>
  </button>
</template>

<style scoped>
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
