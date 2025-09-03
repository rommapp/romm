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
} from "vue";
import { useDisplay } from "vuetify";
import type { SearchRomSchema } from "@/__generated__";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import Flags from "@/components/common/Game/Card/Flags.vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import { ROUTES } from "@/plugins/router";
import storeCollections from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";

const EXTENSION_REGEX = /\.png|\.jpg|\.jpeg$/;

const props = withDefaults(
  defineProps<{
    rom: SimpleRom | SearchRomSchema;
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
  props.rom.igdb_id || props.rom.moby_id || props.rom.ss_id
    ? getMissingCoverImage(props.rom.name || props.rom.slug || "")
    : getUnmatchedCoverImage(props.rom.name || props.rom.slug || ""),
);
const activeMenu = ref(false);

const showActionBarAlways = useLocalStorage("settings.showActionBar", false);
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

const isWebpEnabled =
  heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP;

const largeCover = computed(() => {
  if (!romsStore.isSimpleRom(props.rom))
    return (
      props.rom.igdb_url_cover ||
      props.rom.moby_url_cover ||
      props.rom.ss_url_cover
    );
  const pathCoverLarge = isWebpEnabled
    ? props.rom.path_cover_large?.replace(EXTENSION_REGEX, ".webp")
    : props.rom.path_cover_large;
  return pathCoverLarge || "";
});

const smallCover = computed(() => {
  if (!romsStore.isSimpleRom(props.rom)) return "";
  const pathCoverSmall = isWebpEnabled
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
});
</script>

<template>
  <v-hover v-slot="{ isHovering: isOuterHovering, props: hoverProps }">
    <div data-tilt ref="tilt-card-ref">
      <v-card
        :style="{
          ...(disableViewTransition
            ? {}
            : { viewTransitionName: `card-${rom.id}` }),
        }"
        :minWidth="width"
        :maxWidth="width"
        :minHeight="height"
        :maxHeight="height"
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
        :elevation="isOuterHovering && transformScale ? 20 : 3"
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
      >
        <v-card-text class="pa-0">
          <v-hover v-slot="{ isHovering, props }" open-delay="800">
            <v-img
              @click="handleClick"
              @touchstart="handleTouchStart"
              @touchend="handleTouchEnd"
              v-bind="props"
              cover
              content-class="d-flex flex-column justify-space-between"
              :class="{ pointer: pointerOnHover }"
              :key="romsStore.isSimpleRom(rom) ? rom.updated_at : ''"
              :src="largeCover || fallbackCoverImage"
              :aspect-ratio="computedAspectRatio"
            >
              <template v-bind="props" v-if="titleOnHover">
                <v-expand-transition>
                  <div
                    v-if="
                      isHovering ||
                      (romsStore.isSimpleRom(rom) && !rom.path_cover_large) ||
                      (!romsStore.isSimpleRom(rom) &&
                        !rom.igdb_url_cover &&
                        !rom.moby_url_cover &&
                        !rom.ss_url_cover &&
                        !rom.sgdb_url_cover)
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
                  <sources v-if="!romsStore.isSimpleRom(rom)" :rom="rom" />
                  <flags
                    v-if="romsStore.isSimpleRom(rom) && showChips"
                    :rom="rom"
                  />
                </v-col>
              </v-row>
              <div v-bind="props">
                <v-row
                  v-if="romsStore.isSimpleRom(rom) && showChips"
                  no-gutters
                >
                  <v-col cols="auto" class="px-0">
                    <platform-icon
                      v-if="showPlatformIcon"
                      :size="25"
                      :key="rom.platform_slug"
                      :slug="rom.platform_slug"
                      :name="rom.platform_name"
                      :fs-slug="rom.platform_fs_slug"
                      class="ml-1"
                    />
                  </v-col>
                  <v-col class="px-1 d-flex justify-end">
                    <missing-from-f-s-icon
                      v-if="rom.missing_from_fs"
                      :text="`Missing from filesystem: ${rom.fs_path}/${rom.fs_name}`"
                      class="mr-1 mb-1 px-1"
                      chip
                      chipDensity="compact"
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
                  <slot name="append-inner-right"> </slot>
                </div>
                <v-expand-transition>
                  <action-bar
                    v-if="
                      romsStore.isSimpleRom(rom) &&
                      showActionBar &&
                      !showActionBarAlways &&
                      (isOuterHovering || activeMenu) &&
                      !smAndDown
                    "
                    class="translucent"
                    @menu-open="handleOpenMenu"
                    @menu-close="handleCloseMenu"
                    :rom="rom"
                    :sizeActionBar="sizeActionBar"
                  />
                </v-expand-transition>
              </div>
              <template #placeholder>
                <v-img
                  cover
                  eager
                  :src="smallCover || fallbackCoverImage"
                  :aspect-ratio="computedAspectRatio"
                >
                  <template #placeholder>
                    <skeleton
                      :platformId="rom.platform_id"
                      :aspectRatio="computedAspectRatio"
                      type="image"
                    />
                  </template>
                </v-img>
              </template>
              <template #error>
                <v-img
                  cover
                  eager
                  :src="fallbackCoverImage"
                  :aspect-ratio="computedAspectRatio"
                />
              </template>
            </v-img>
          </v-hover>
        </v-card-text>
        <action-bar
          v-if="
            (smAndDown || showActionBarAlways) &&
            showActionBar &&
            romsStore.isSimpleRom(rom)
          "
          :rom="rom"
          :sizeActionBar="sizeActionBar"
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
