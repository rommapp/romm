<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import VanillaTilt from "vanilla-tilt";
import {
  computed,
  ref,
  onMounted,
  onBeforeUnmount,
  inject,
  useTemplateRef,
  nextTick,
} from "vue";
import { useDisplay } from "vuetify";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import Flags from "@/components/common/Game/Card/Flags.vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { useGameAnimation } from "@/composables/useGameAnimation";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { SimpleRom, SearchRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import {
  getMissingCoverImage,
  getUnmatchedCoverImage,
  EXTENSION_REGEX,
} from "@/utils/covers";

const props = withDefaults(
  defineProps<{
    rom: SimpleRom | SearchRom;
    coverSrc?: string;
    aspectRatio?: string | number;
    width?: string | number;
    height?: string | number;
    transformScale?: boolean;
    titleOnHover?: boolean;
    pointerOnHover?: boolean;
    showChips?: boolean;
    showPlatformIcon?: boolean;
    showActionBar?: boolean;
    sizeActionBar?: number;
    withBorderPrimary?: boolean;
    withLink?: boolean;
    disableViewTransition?: boolean;
    enable3DTilt?: boolean;
  }>(),
  {
    coverSrc: undefined,
    aspectRatio: undefined,
    width: undefined,
    height: undefined,
    transformScale: false,
    titleOnHover: false,
    pointerOnHover: false,
    showChips: false,
    showPlatformIcon: true,
    showActionBar: true,
    sizeActionBar: 0,
    withBorderPrimary: false,
    disableViewTransition: false,
    enable3DTilt: false,
    withLink: false,
  },
);

const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const romsStore = storeRoms();
const emitter = inject<Emitter<Events>>("emitter");
const emit = defineEmits([
  "hover",
  "openedmenu",
  "closedmenu",
  "click",
  "touchstart",
  "touchend",
]);
const handleClick = (event: MouseEvent) => {
  if (event.button === 0) {
    // Only handle left-click
    emit("click", { event: event, rom: props.rom });
  }
};
const handleTouchStart = (event: TouchEvent) => {
  emit("touchstart", { event: event, rom: props.rom });
};
const handleTouchEnd = (event: TouchEvent) => {
  emit("touchend", { event: event, rom: props.rom });
};
const handleOpenMenu = () => {
  activeMenu.value = true;
  emit("openedmenu", { openedMenu: true, id: props.rom.id });
};
const handleCloseMenu = () => {
  activeMenu.value = false;
  emit("closedmenu");
};

const galleryViewStore = storeGalleryView();
const collectionsStore = storeCollections();
const heartbeatStore = storeHeartbeat();

const computedAspectRatio = computed(() => {
  const ratio =
    props.aspectRatio ||
    platformsStore.getAspectRatio(props.rom.platform_id) ||
    galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
});
const fallbackCoverImage = computed(() =>
  props.rom.is_identified
    ? getMissingCoverImage(props.rom.name || props.rom.slug || "")
    : getUnmatchedCoverImage(props.rom.name || props.rom.slug || ""),
);
const activeMenu = ref(false);

const showActionBarAlways = useLocalStorage("settings.showActionBar", false);
const showGameTitleAlways = useLocalStorage("settings.showGameTitle", false);
const showSiblings = useLocalStorage("settings.showSiblings", true);

const hasNotes = computed(() => {
  if (!romsStore.isSimpleRom(props.rom)) return false;
  return (
    props.rom.rom_user?.note_raw_markdown &&
    props.rom.rom_user.note_raw_markdown.trim().length > 0
  );
});

// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}

const tiltCardRef = useTemplateRef<TiltHTMLElement>("tilt-card-ref");
const vImgRef = useTemplateRef("game-image-ref");

const gameIsHovering = ref(false);
const {
  boxartStyleCover,
  animateCD,
  animateCartridge,
  animateCDSpin,
  animateCDLoad,
  stopCDAnimation,
  animateLoadCart,
} = useGameAnimation({
  rom: props.rom,
  accelerate: gameIsHovering,
  coverSrc: props.coverSrc,
  vImgRef: vImgRef,
});

const boxartStyle = useLocalStorage<BoxartStyleOption>(
  "settings.boxartStyle",
  "cover",
);

const localVideoPath = computed(() => {
  if (!romsStore.isSimpleRom(props.rom)) return null;
  // Only play video if boxart style is miximage
  if (boxartStyle.value !== "miximage_path") return null;
  const ssVideo = props.rom.ss_metadata?.video_path;
  const gamelistVideo = props.rom.gamelist_metadata?.video_path;
  return ssVideo || gamelistVideo || null;
});

const hoverTimeout = ref<ReturnType<typeof setTimeout> | null>(null);
const isVideoPlaying = ref(false);
const videoRef = useTemplateRef<HTMLVideoElement>("hover-video-ref");

const isWebpEnabled = computed(
  () => heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
);

const largeCover = computed(() => {
  if (props.coverSrc) return props.coverSrc;
  if (boxartStyleCover.value)
    return `${FRONTEND_RESOURCES_PATH}/${boxartStyleCover.value}`;
  if (!romsStore.isSimpleRom(props.rom)) {
    return (
      props.rom.igdb_url_cover ||
      props.rom.moby_url_cover ||
      props.rom.ss_url_cover ||
      props.rom.launchbox_url_cover ||
      props.rom.flashpoint_url_cover
    );
  }
  const pathCoverLarge = isWebpEnabled.value
    ? props.rom.path_cover_large?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_large;
  return pathCoverLarge || "";
});

const smallCover = computed(() => {
  if (props.coverSrc) return props.coverSrc;
  if (boxartStyleCover.value)
    return `${FRONTEND_RESOURCES_PATH}/${boxartStyleCover.value}`;
  if (!romsStore.isSimpleRom(props.rom)) return "";
  const pathCoverSmall = isWebpEnabled.value
    ? props.rom.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_small;
  return pathCoverSmall || "";
});

const showNoteDialog = (event: MouseEvent | KeyboardEvent) => {
  event.preventDefault();
  if (romsStore.isSimpleRom(props.rom)) {
    emitter?.emit("showNoteDialog", props.rom);
  }
};

const onMouseEnter = () => {
  gameIsHovering.value = true;
  animateCDSpin();
};

const onCardMouseEnter = () => {
  if (isVideoPlaying.value) return;
  // Start video after 3 seconds if video path exists
  if (localVideoPath.value) {
    hoverTimeout.value = setTimeout(async () => {
      isVideoPlaying.value = true;
      // Wait for next tick to ensure video element is rendered
      await nextTick();
      if (videoRef.value) {
        videoRef.value.load();
        videoRef.value.play().catch(() => {
          // Handle play() promise rejection (e.g., autoplay disabled)
          isVideoPlaying.value = false;
        });
      }
    }, 2000);
  }
};

const onMouseLeave = () => {
  gameIsHovering.value = false;
};

const onCardMouseLeave = () => {
  // Clear the hover timeout if it exists
  if (hoverTimeout.value) {
    clearTimeout(hoverTimeout.value);
    hoverTimeout.value = null;
  }

  // Pause and reset video
  if (videoRef.value) {
    videoRef.value.pause();
    videoRef.value.currentTime = 0;
  }

  isVideoPlaying.value = false;
};

const handlePlayGame = (romId: number) => {
  if (romId !== props.rom.id) return;
  if (animateCD.value) {
    animateCDSpin();
    animateCDLoad();
  } else if (animateCartridge.value) {
    animateLoadCart();
  }
};

emitter?.on("playGame", handlePlayGame);

onMounted(() => {
  if (tiltCardRef.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCardRef.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCardRef.value?.vanillaTilt && props.enable3DTilt) {
    tiltCardRef.value.vanillaTilt.destroy();
  }
  emitter?.off("playGame", handlePlayGame);
  stopCDAnimation();

  // Clean up hover timeout
  if (hoverTimeout.value) {
    clearTimeout(hoverTimeout.value);
    hoverTimeout.value = null;
  }

  // Clean up video
  if (videoRef.value) {
    videoRef.value.pause();
    videoRef.value.src = "";
  }
});
</script>

<template>
  <v-hover v-slot="{ isHovering: isOuterHovering, props: hoverProps }">
    <div ref="tilt-card-ref" data-tilt>
      <v-card
        :style="{
          ...(disableViewTransition
            ? {}
            : { viewTransitionName: `card-${rom.id}` }),
        }"
        :min-width="width"
        :max-width="width"
        :min-height="height"
        :max-height="height"
        v-bind="{
          ...hoverProps,
          ...(withLink && rom.id
            ? {
                to: { name: ROUTES.ROM, params: { rom: rom.id } },
              }
            : {}),
        }"
        class="bg-transparent"
        :class="{
          'on-hover': isOuterHovering || activeMenu,
          'border-selected': withBorderPrimary,
          'transform-scale': transformScale && !enable3DTilt,
        }"
        :elevation="
          isOuterHovering && transformScale ? 20 : boxartStyleCover ? 0 : 3
        "
        :aria-label="`${rom.name} game card`"
        @mouseenter="
          () => {
            emit('hover', { isHovering: true, id: rom.id });
          }
        "
        @mouseleave="
          () => {
            emit('hover', { isHovering: false, id: rom.id });
          }
        "
        @blur="
          () => {
            emit('hover', { isHovering: false, id: rom.id });
          }
        "
      >
        <v-card-text
          class="pa-0 position-relative"
          @mouseenter="onCardMouseEnter"
          @mouseleave="onCardMouseLeave"
        >
          <v-hover v-slot="{ isHovering, props: imgProps }" open-delay="800">
            <v-img
              ref="game-image-ref"
              v-bind="imgProps"
              :key="romsStore.isSimpleRom(rom) ? rom.id : rom.name"
              :cover="!boxartStyleCover"
              :contain="boxartStyleCover"
              content-class="d-flex flex-column justify-space-between"
              :class="{
                pointer: pointerOnHover,
                'opacity-0': isVideoPlaying && localVideoPath,
                transitioning: !isVideoPlaying && localVideoPath,
              }"
              :src="largeCover || fallbackCoverImage"
              :aspect-ratio="computedAspectRatio"
              @click="handleClick"
              @touchstart="handleTouchStart"
              @touchend="handleTouchEnd"
              @mouseenter="onMouseEnter"
              @mouseleave="onMouseLeave"
            >
              <template v-if="titleOnHover">
                <v-expand-transition>
                  <div
                    v-if="
                      isHovering ||
                      showGameTitleAlways ||
                      (romsStore.isSimpleRom(rom) && !rom.path_cover_large) ||
                      (!romsStore.isSimpleRom(rom) &&
                        !rom.igdb_url_cover &&
                        !rom.moby_url_cover &&
                        !rom.ss_url_cover &&
                        !rom.sgdb_url_cover &&
                        !rom.launchbox_url_cover &&
                        !rom.flashpoint_url_cover)
                    "
                    class="translucent text-white"
                    :class="
                      sizeActionBar === 1 ? 'text-subtitle-1' : 'text-caption'
                    "
                    :title="
                      romsStore.isSimpleRom(rom) && rom.name === rom.fs_name
                        ? rom.fs_name_no_tags
                        : rom.name || ''
                    "
                  >
                    <div class="pa-2 text-truncate">
                      {{
                        romsStore.isSimpleRom(rom) && rom.name === rom.fs_name
                          ? rom.fs_name_no_tags
                          : rom.name
                      }}
                    </div>
                  </div>
                </v-expand-transition>
              </template>
              <v-row no-gutters class="text-white px-1">
                <v-col>
                  <Sources v-if="!romsStore.isSimpleRom(rom)" :rom="rom" />
                  <Flags
                    v-if="romsStore.isSimpleRom(rom) && showChips"
                    :rom="rom"
                  />
                </v-col>
              </v-row>
              <div>
                <v-row
                  v-if="romsStore.isSimpleRom(rom) && showChips"
                  no-gutters
                >
                  <v-col cols="auto" class="px-0">
                    <PlatformIcon
                      v-if="showPlatformIcon"
                      :key="rom.platform_slug"
                      :size="25"
                      :slug="rom.platform_slug"
                      :name="rom.platform_display_name"
                      :fs-slug="rom.platform_fs_slug"
                      class="ml-1"
                    />
                  </v-col>
                  <v-col class="px-1 d-flex justify-end">
                    <MissingFromFSIcon
                      v-if="rom.missing_from_fs"
                      :text="`Missing from filesystem: ${rom.fs_path}/${rom.fs_name}`"
                      class="mr-1 mb-1 px-1"
                      chip
                      chip-density="compact"
                    />
                    <v-chip
                      v-if="rom.hasheous_id"
                      class="translucent text-white mr-1 mb-1 px-1"
                      density="compact"
                      title="Verified with Hasheous"
                    >
                      <v-icon>mdi-check-decagram-outline</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="rom.siblings.length > 0 && showSiblings"
                      class="translucent text-white mr-1 mb-1 px-1"
                      density="compact"
                      :title="`${rom.siblings.length} sibling(s)`"
                    >
                      <v-icon>mdi-card-multiple-outline</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="collectionsStore.isFavorite(rom)"
                      text="Favorite"
                      color="secondary"
                      density="compact"
                      class="translucent text-white mr-1 mb-1 px-1"
                    >
                      <v-icon>mdi-star</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="hasNotes && showChips"
                      class="translucent text-white mr-1 mb-1 px-1"
                      density="compact"
                      title="View notes"
                      @click.stop="showNoteDialog"
                    >
                      <v-icon>mdi-notebook</v-icon>
                    </v-chip>
                  </v-col>
                </v-row>
                <div class="position-absolute append-inner-right">
                  <slot name="append-inner-right" />
                </div>
                <v-expand-transition>
                  <ActionBar
                    v-if="
                      romsStore.isSimpleRom(rom) &&
                      showActionBar &&
                      (isOuterHovering ||
                        showActionBarAlways ||
                        activeMenu ||
                        smAndDown)
                    "
                    class="translucent"
                    :rom="rom"
                    :size-action-bar="sizeActionBar"
                    @menu-open="handleOpenMenu"
                    @menu-close="handleCloseMenu"
                  />
                </v-expand-transition>
              </div>
              <template #placeholder>
                <v-img
                  :cover="!boxartStyleCover"
                  :contain="boxartStyleCover"
                  eager
                  :src="smallCover || fallbackCoverImage"
                  :aspect-ratio="computedAspectRatio"
                >
                  <template #placeholder>
                    <Skeleton
                      :platform-id="rom.platform_id"
                      :aspect-ratio="computedAspectRatio"
                      type="image"
                    />
                  </template>
                </v-img>
              </template>
              <template #error>
                <v-img
                  :cover="!boxartStyleCover"
                  :contain="boxartStyleCover"
                  eager
                  :src="fallbackCoverImage"
                  :aspect-ratio="computedAspectRatio"
                />
              </template>
            </v-img>
            <div
              class="hover-video-container position-absolute top-0 opacity-0 h-full d-flex align-center justify-center"
              :class="{
                'opacity-100 transitioning': isVideoPlaying && localVideoPath,
              }"
            >
              <div
                class="position-relative max-h-full"
                style="margin-top: -40px"
              >
                <video
                  ref="hover-video-ref"
                  :src="`${FRONTEND_RESOURCES_PATH}/${localVideoPath}`"
                  class="hover-video"
                  loop
                  :autoplay="isVideoPlaying"
                  playsinline
                  preload="none"
                />
                <img
                  src="/assets/default/miximage.png"
                  style="z-index: 1"
                  class="position-relative"
                />
              </div>
            </div>
          </v-hover>
        </v-card-text>
      </v-card>
    </div>
  </v-hover>
</template>

<style scoped>
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: max-height 0.5s;
}

.expand-on-hover:hover {
  max-height: 1000px;
}

.v-expand-transition-enter-active,
.v-expand-transition-leave-active {
  transition: max-height 0.5s;
}

.v-expand-transition-enter,
.v-expand-transition-leave-to {
  max-height: 0;
  overflow: hidden;
}

.v-img {
  user-select: none;
  transition: opacity 0.25s ease;
}

.append-inner-right {
  bottom: 0rem;
  right: 0rem;
}

.v-chip:hover {
  transform: scale(1.1);
  transition: transform 0.2s ease;
}

.hover-video-container {
  transition: opacity 0.25s ease;
  transition-delay: 0.1s;
}

.v-img.transitioning,
.hover-video-container.transitioning {
  transition-delay: 0.1s;
}

.hover-video {
  position: absolute;
  top: 3%;
  left: 2%;
  width: 96%;
  height: 94%;
  background: black;
  object-fit: contain;
  pointer-events: none;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
