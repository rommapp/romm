<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
  watchEffect,
  useTemplateRef,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import {
  collectionElementRegistry,
  smartCollectionElementRegistry,
  virtualCollectionElementRegistry,
} from "@/console/composables/useElementRegistry";
import type { CollectionType } from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import {
  getCollectionCoverImage,
  getFavoriteCoverImage,
  EXTENSION_REGEX,
} from "@/utils/covers";

const { t } = useI18n();
const props = defineProps<{
  collection: CollectionType;
  index: number;
  selected?: boolean;
  loaded?: boolean;
}>();
const emit = defineEmits([
  "click",
  "mouseenter",
  "focus",
  "loaded",
  "select",
  "deselect",
]);
const collectionCardRef = useTemplateRef<HTMLButtonElement>(
  "collection-card-ref",
);

const heartbeatStore = storeHeartbeat();

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
});

const fallbackCollectionCover = computed(() =>
  props.collection.is_favorite
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  // Check if it's a regular collection with covers or a smart collection with covers
  const isRegularOrSmartWithCovers =
    !props.collection.is_virtual &&
    props.collection.path_cover_large &&
    props.collection.path_cover_small;

  const isWebpEnabled =
    heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP;
  const pathCoverLarge = isWebpEnabled
    ? props.collection.path_cover_large?.replace(EXTENSION_REGEX, ".webp")
    : props.collection.path_cover_large;
  const pathCoverSmall = isWebpEnabled
    ? props.collection.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.collection.path_cover_small;

  if (isRegularOrSmartWithCovers) {
    memoizedCovers.value = {
      large: [pathCoverLarge || "", pathCoverLarge || ""],
      small: [pathCoverSmall || "", pathCoverSmall || ""],
    };
    return;
  }

  // Handle virtual collections which have plural covers arrays
  const largeCoverUrls = props.collection.path_covers_large.map((url) =>
    isWebpEnabled ? url.replace(EXTENSION_REGEX, ".webp") : url,
  );
  const smallCoverUrls = props.collection.path_covers_small.map((url) =>
    isWebpEnabled ? url.replace(EXTENSION_REGEX, ".webp") : url,
  );

  if (largeCoverUrls.length < 2) {
    memoizedCovers.value = {
      large: [fallbackCollectionCover.value, fallbackCollectionCover.value],
      small: [fallbackCollectionCover.value, fallbackCollectionCover.value],
    };
    return;
  }

  const shuffledLarge = [...largeCoverUrls].sort(() => Math.random() - 0.5);
  const shuffledSmall = [...smallCoverUrls].sort(() => Math.random() - 0.5);

  memoizedCovers.value = {
    large: [shuffledLarge[0], shuffledLarge[1]],
    small: [shuffledSmall[0], shuffledSmall[1]],
  };
});

const firstLargeCover = computed(() => memoizedCovers.value.large[0]);
const secondLargeCover = computed(() => memoizedCovers.value.large[1]);

watch(
  () => props.selected,
  (isSelected) => {
    if (
      isSelected &&
      firstLargeCover.value &&
      firstLargeCover.value !== fallbackCollectionCover.value
    ) {
      emit("select", firstLargeCover.value);
    } else if (isSelected) {
      emit("deselect");
    }
  },
  { immediate: true },
);

onMounted(() => {
  if (!collectionCardRef.value) return;
  if (props.collection.is_smart) {
    smartCollectionElementRegistry.registerElement(
      props.index,
      collectionCardRef.value,
    );
  } else if (props.collection.is_virtual) {
    virtualCollectionElementRegistry.registerElement(
      props.index,
      collectionCardRef.value,
    );
  } else {
    collectionElementRegistry.registerElement(
      props.index,
      collectionCardRef.value,
    );
  }
});
</script>

<template>
  <div class="flex flex-col items-center w-[250px] shrink-0">
    <button
      ref="collection-card-ref"
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
        <!-- Split cover display for virtual collections or collections without single covers -->
        <template
          v-if="
            collection.is_virtual ||
            !collection.path_cover_large ||
            !collection.path_cover_small
          "
        >
          <div class="absolute inset-0">
            <img
              class="absolute inset-0 w-full h-full object-cover [clip-path:polygon(0_0,100%_0,0_100%,0_100%)]"
              :src="firstLargeCover"
              :alt="collection.name + ' cover 1'"
              loading="lazy"
              @load="emit('loaded')"
              @error="emit('loaded')"
            />
            <img
              class="absolute inset-0 w-full h-full object-cover [clip-path:polygon(0_100%,100%_0,100%_100%)]"
              :src="secondLargeCover"
              :alt="collection.name + ' cover 2'"
              loading="lazy"
              @load="emit('loaded')"
              @error="emit('loaded')"
            />
          </div>
        </template>
        <!-- Standard single cover for regular/smart collections -->
        <img
          v-else
          class="w-full h-full object-cover"
          :src="firstLargeCover"
          :alt="collection.name"
          @load="emit('loaded')"
          @error="emit('loaded')"
        />
        <!-- Fallback (no cover) -->
        <div
          v-if="!firstLargeCover && !secondLargeCover"
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
            {{ t("console.games-n", collection.rom_count || 0) }}
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
