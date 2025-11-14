<script setup lang="ts">
import {
  computed,
  onMounted,
  onBeforeUnmount,
  useTemplateRef,
  watch,
} from "vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import { useGameAnimation } from "@/composables/useGameAnimation";
import {
  continuePlayingElementRegistry,
  gamesListElementRegistry,
} from "@/console/composables/useElementRegistry";
import storeCollections from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import { type SimpleRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import {
  EXTENSION_REGEX,
  getMissingCoverImage,
  getUnmatchedCoverImage,
} from "@/utils/covers";

const props = defineProps<{
  rom: SimpleRom;
  index: number;
  selected?: boolean;
  loaded?: boolean;
  continuePlaying?: boolean;
  registry?: "continuePlaying" | "gamesList";
}>();

const heartbeatStore = storeHeartbeat();
const gameCardRef = useTemplateRef<HTMLButtonElement>("game-card-ref");
const coverRef = useTemplateRef("game-image-ref");
const videoRef = useTemplateRef<HTMLVideoElement>("hover-video-ref");

const isWebpEnabled = computed(
  () => heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
);

const {
  boxartStyleCover,
  localVideoPath,
  isVideoPlaying,
  stopCDAnimation,
  stopVideo,
} = useGameAnimation({
  rom: props.rom,
  isHovering: computed(() => props.selected),
  coverRef: coverRef,
  videoRef: videoRef,
});

const largeCover = computed(() => {
  if (boxartStyleCover.value)
    return `${FRONTEND_RESOURCES_PATH}/${boxartStyleCover.value}`;
  const pathCoverLarge = isWebpEnabled.value
    ? props.rom.path_cover_large?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_large;
  return pathCoverLarge || "";
});

const smallCover = computed(() => {
  if (boxartStyleCover.value)
    return `${FRONTEND_RESOURCES_PATH}/${boxartStyleCover.value}`;
  const pathCoverSmall = isWebpEnabled.value
    ? props.rom.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_small;
  return pathCoverSmall || "";
});

const fallbackCoverImage = computed(() =>
  props.rom.is_identified
    ? getMissingCoverImage(props.rom.name || props.rom.slug || "")
    : getUnmatchedCoverImage(props.rom.name || props.rom.slug || ""),
);

const emit = defineEmits([
  "click",
  "mouseenter",
  "focus",
  "loaded",
  "select",
  "deselect",
]);

// Check if this game is in the favorites collection
const collectionsStore = storeCollections();
const isFavorited = computed(() => {
  return collectionsStore.isFavorite(props.rom);
});

// Watch for selection changes and emit events
watch(
  () => props.selected,
  (isSelected) => {
    if (isSelected) {
      if (largeCover.value) {
        emit("select", largeCover.value);
      }
    } else {
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
    continuePlayingElementRegistry.registerElement(
      props.index,
      gameCardRef.value,
    );
  }
});

onBeforeUnmount(() => {
  stopCDAnimation();
  stopVideo();
});
</script>

<template>
  <button
    ref="game-card-ref"
    class="relative block border-2 border-white/10 rounded-md p-0 cursor-pointer overflow-hidden transition-all duration-200"
    :class="{
      '-translate-y-[2px] scale-[1.03] shadow-[0_8px_28px_rgba(0,0,0,0.35),_0_0_0_2px_var(--console-game-card-focus-border),_0_0_16px_var(--console-game-card-focus-border)]':
        selected,
      'w-[250px] shrink-0': continuePlaying,
      'shadow-[0_4px_20px_rgba(0,0,0,0.3),_inset_0_1px_0_rgba(255,255,255,0.1)]':
        !boxartStyleCover,
    }"
    @click="emit('click')"
    @focus="emit('focus')"
  >
    <div class="w-full h-[350px] relative overflow-hidden rounded">
      <v-img
        ref="game-image-ref"
        class="w-full h-full"
        :cover="!boxartStyleCover"
        :contain="boxartStyleCover"
        :class="{
          'opacity-0': isVideoPlaying && localVideoPath,
          transitioning: !isVideoPlaying && localVideoPath,
        }"
        :src="largeCover || fallbackCoverImage"
        :alt="rom.name || 'Game'"
        @load="emit('loaded')"
        @error="emit('loaded')"
      >
        <template #placeholder>
          <v-img
            eager
            :src="smallCover || fallbackCoverImage"
            :cover="!boxartStyleCover"
            :contain="boxartStyleCover"
          >
            <template #placeholder>
              <Skeleton :platform-id="rom.platform_id" type="image" />
            </template>
          </v-img>
        </template>
        <template #error>
          <v-img cover eager :src="fallbackCoverImage" />
        </template>
      </v-img>
      <div
        v-if="localVideoPath"
        class="hover-video-container absolute top-0 opacity-0 h-full flex items-center justify-center"
        :class="{
          'opacity-100 transitioning': isVideoPlaying,
        }"
      >
        <div class="relative max-h-full" style="margin-top: -40px">
          <video
            ref="hover-video-ref"
            :src="`${FRONTEND_RESOURCES_PATH}/${localVideoPath}`"
            class="hover-video absolute"
            loop
            playsinline
            preload="none"
          />
          <img
            src="/assets/default/miximage.png"
            style="z-index: 1"
            class="relative"
          />
        </div>
      </div>
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
        v-if="!largeCover && !smallCover"
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
              ? new Date(rom.metadatum.first_release_date).getFullYear()
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

.v-img {
  transition: opacity 0.25s ease;
}

.hover-video-container {
  top: 15%;
  transition: opacity 0.25s ease;
  pointer-events: none;
}

.v-img.transitioning,
.hover-video-container.transitioning {
  transition-delay: 0.1s;
}

.hover-video {
  margin-top: 2%;
  left: 2%;
  height: 96%;
  width: 96%;
  border-radius: 4px;
  object-fit: contain;
  pointer-events: none;
  background: black;
}
</style>
