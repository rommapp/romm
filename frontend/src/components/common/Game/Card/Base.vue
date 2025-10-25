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
import type { SearchRomSchema } from "@/__generated__";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import Flags from "@/components/common/Game/Card/Flags.vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH, CD_BASED_SYSTEMS } from "@/utils";
import {
  getMissingCoverImage,
  getUnmatchedCoverImage,
  EXTENSION_REGEX,
} from "@/utils/covers";

const props = withDefaults(
  defineProps<{
    rom: SimpleRom | SearchRomSchema;
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
  // Only handle left-click
  if (event.button === 0) {
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
const boxartStyle = useLocalStorage<BoxartStyleOption>(
  "settings.boxartStyle",
  "cover",
);

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

const isWebpEnabled = computed(
  () => heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
);

// User selected alternative cover image
const boxartStyleCover = computed(() => {
  if (
    props.coverSrc ||
    !romsStore.isSimpleRom(props.rom) ||
    boxartStyle.value === "cover"
  )
    return null;
  const ssMedia = props.rom.ss_metadata?.[boxartStyle.value];
  const gamelistMedia = props.rom.gamelist_metadata?.[boxartStyle.value];
  return ssMedia || gamelistMedia;
});

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

// Spinning disk animation variables
const maxRotationSpeed = 5600; // deg/sec (adjust top speed)
const accelerationRate = 1500; // deg/sec^2 (how fast it accelerates)
const decelerationRate = -2000; // deg/sec^2 (how fast it slows)

// Stored animation state
let angle = 0; // current rotation in degrees
let velocity = 0; // degrees / second
let lastTimestamp: number | null = null;
let isHovering = false;
let animationId: number | null = null;

const onEnter = () => {
  // Only animate physical disks
  if (boxartStyle.value !== "physical_path") return;
  if (!boxartStyleCover.value) return;
  if (!romsStore.isSimpleRom(props.rom)) return;
  if (!CD_BASED_SYSTEMS.includes(props.rom.platform_slug)) return;

  isHovering = true;
  startAnimation();
};

const onLeave = () => {
  isHovering = false;
};

const step = (timestamp: number) => {
  if (lastTimestamp === null) lastTimestamp = timestamp;
  const deltaTime = (timestamp - lastTimestamp) / 1000; // in seconds
  lastTimestamp = timestamp;

  // Update velocity with acceleration or deceleration
  velocity += (isHovering ? accelerationRate : decelerationRate) * deltaTime;
  if (velocity > maxRotationSpeed) velocity = maxRotationSpeed;
  if (velocity < 0) velocity = 0;

  // Integrate angle
  angle = (angle + velocity * deltaTime) % 360;

  if (tiltCardRef.value) {
    const imageElement = tiltCardRef.value.querySelector(
      ".v-img__img.v-img__img--contain",
    );
    if (imageElement) {
      (imageElement as HTMLImageElement).style.transform =
        `rotate(${angle}deg)`;
    }
  }

  // Only continue animation if we're hovering or still decelerating
  if (isHovering || velocity > 0) {
    animationId = requestAnimationFrame(step);
  }
};

const startAnimation = () => {
  lastTimestamp = null;
  animationId = requestAnimationFrame(step);
};

const stopAnimation = () => {
  if (animationId !== null) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
};

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
  stopAnimation();
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
        <v-card-text class="pa-0">
          <v-hover v-slot="{ isHovering, props: imgProps }" open-delay="800">
            <v-img
              v-bind="imgProps"
              :key="romsStore.isSimpleRom(rom) ? rom.id : rom.name"
              :cover="!boxartStyleCover"
              :contain="boxartStyleCover"
              content-class="d-flex flex-column justify-space-between"
              :class="{ pointer: pointerOnHover }"
              :src="largeCover || fallbackCoverImage"
              :aspect-ratio="computedAspectRatio"
              @click="handleClick"
              @touchstart="handleTouchStart"
              @touchend="handleTouchEnd"
              @mouseenter="onEnter"
              @mouseleave="onLeave"
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
                      !showActionBarAlways &&
                      (isOuterHovering || activeMenu) &&
                      !smAndDown
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
          </v-hover>
        </v-card-text>
        <ActionBar
          v-if="
            (smAndDown || showActionBarAlways) &&
            showActionBar &&
            romsStore.isSimpleRom(rom)
          "
          :rom="rom"
          :size-action-bar="sizeActionBar"
        />
      </v-card>
    </div>
  </v-hover>
</template>

<style scoped>
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: max-height 0.5s; /* Add a transition for a smooth effect */
}

.expand-on-hover:hover {
  max-height: 1000px; /* Adjust to a sufficiently large value to ensure the full expansion */
}

/* Apply styles to v-expand-transition component */
.v-expand-transition-enter-active,
.v-expand-transition-leave-active {
  transition: max-height 0.5s;
}

.v-expand-transition-enter, .v-expand-transition-leave-to /* .v-expand-transition-leave-active in <2.1.8 */ {
  max-height: 0; /* Set max-height to 0 when entering or leaving */
  overflow: hidden;
}

.v-img {
  user-select: none; /* Prevents text selection */
  -webkit-user-select: none; /* Safari */
  -moz-user-select: none; /* Firefox */
  -ms-user-select: none; /* Internet Explorer/Edge */
}

.append-inner-right {
  bottom: 0rem;
  right: 0rem;
}

/* Note icon hover effect */
.v-chip:hover {
  transform: scale(1.1);
  transition: transform 0.2s ease;
}
</style>
