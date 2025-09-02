<script setup lang="ts">
import type { CollectionSchema } from "@/__generated__/models/CollectionSchema";
import { collectionElementRegistry } from "@/console/composables/useElementRegistry";
import { getFavoriteCoverImage } from "@/utils/covers";
import { computed, onMounted, ref, watchEffect } from "vue";

const props = defineProps<{
  collection: CollectionSchema;
  index: number;
  selected?: boolean;
  loaded?: boolean;
}>();
const emit = defineEmits(["click", "mouseenter", "focus", "loaded"]);
const el = ref<HTMLElement>();

const isFavorite = computed(() => props.collection.is_favorite);
const coverSrc = computed(
  () =>
    props.collection.path_cover_large ||
    props.collection.path_cover_small ||
    props.collection.url_cover ||
    "",
);

// Composite favourite logic (two diagonally split images)
const firstCover = ref("");
const secondCover = ref("");
const compositeReady = ref(false);

watchEffect(() => {
  if (!isFavorite.value) {
    compositeReady.value = false;
    return;
  }
  const large = props.collection.path_covers_large || [];
  const small = props.collection.path_covers_small || [];
  // Choose source list preferring large
  const source = large.length ? large : small;
  if (source.length >= 2) {
    const shuffled = [...source].sort(() => Math.random() - 0.5);
    firstCover.value = shuffled[0];
    secondCover.value = shuffled[1];
  } else if (source.length === 1) {
    firstCover.value = source[0];
    secondCover.value = getFavoriteCoverImage(props.collection.name);
  } else {
    const gen = getFavoriteCoverImage(props.collection.name);
    firstCover.value = gen;
    secondCover.value = gen;
  }
  compositeReady.value = true;
});

onMounted(() => {
  if (!el.value) return;
  collectionElementRegistry.registerElement(props.index, el.value);
});
</script>

<template>
  <div class="flex flex-col items-center w-[250px] shrink-0">
    <button
      ref="el"
      class="relative block bg-[var(--console-collection-card-bg)] border-2 border-white/10 rounded-md p-0 cursor-pointer overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)] transition-all duration-200 w-full"
      :class="{
        '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--console-collection-card-focus-border),_0_0_16px_var(--console-collection-card-focus-border)]':
          selected,
      }"
      @click="emit('click')"
      @focus="emit('focus')"
    >
      <div
        class="w-full h-[350px] relative overflow-hidden rounded"
        :style="{ backgroundColor: 'var(--console-collection-card-bg)' }"
      >
        <!-- Favourite composite cover -->
        <template v-if="isFavorite && compositeReady">
          <div class="absolute inset-0">
            <img
              class="absolute inset-0 w-full h-full object-cover [clip-path:polygon(0_0,100%_0,0_100%,0_100%)]"
              :src="firstCover"
              :alt="collection.name + ' cover 1'"
              loading="lazy"
            />
            <img
              class="absolute inset-0 w-full h-full object-cover [clip-path:polygon(0_100%,100%_0,100%_100%)]"
              :src="secondCover"
              :alt="collection.name + ' cover 2'"
              loading="lazy"
            />
          </div>
        </template>
        <!-- Standard single cover -->
        <img
          v-else-if="coverSrc"
          class="w-full h-full object-cover"
          :src="coverSrc"
          :alt="collection.name"
          @load="emit('loaded')"
          @error="emit('loaded')"
        />
        <!-- Fallback (no cover) -->
        <div
          v-else
          class="w-full h-full flex items-center justify-center"
          :style="{ background: 'var(--console-collection-card-bg-fallback)' }"
        >
          <div class="flex flex-col items-center justify-center select-none">
            <div class="text-3xl mb-2">🗂️</div>
            <div
              class="font-semibold text-center px-3 line-clamp-2"
              :style="{ color: 'var(--console-card-text)' }"
            >
              {{ collection.name }}
            </div>
          </div>
        </div>
        <!-- Selected highlight radial glow -->
        <div
          class="absolute inset-0 opacity-0 pointer-events-none"
          :style="{
            background:
              'radial-gradient(circle at center, var(--console-collection-card-focus-border) 0%, transparent 70%)',
          }"
          :class="{ 'opacity-10': selected }"
        />
        <div
          v-if="!loaded"
          class="absolute inset-0 bg-gradient-to-r from-white/10 via-white/20 to-white/10 bg-[length:200%_100%] animate-[shimmer_1.2s_linear_infinite]"
        />
        <div
          class="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-b from-transparent to-black/75 text-sm leading-tight z-10"
          :style="{ color: 'var(--console-collection-card-text)' }"
        >
          <div
            class="text-xs opacity-90"
            :style="{ color: 'var(--console-collection-card-text)' }"
          >
            {{ collection.rom_count || 0 }} games
          </div>
        </div>
      </div>
    </button>
    <div
      class="mt-2 w-full text-center text-sm font-medium px-1 line-clamp-2 select-none"
      :class="selected ? 'drop-shadow' : ''"
      :style="{
        color: selected
          ? 'var(--console-collection-card-text-secondary)'
          : 'var(--console-collection-card-text)',
      }"
    >
      {{ collection.name }}
    </div>
  </div>
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

button:focus {
  outline: none;
}
</style>
