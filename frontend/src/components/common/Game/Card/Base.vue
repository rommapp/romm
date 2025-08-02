<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import Flags from "@/components/common/Game/Card/Flags.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import storePlatforms from "@/stores/platforms";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import storeCollections from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import { ROUTES } from "@/plugins/router";
import storeRoms from "@/stores/roms";
import { type SimpleRom } from "@/stores/roms";
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { isNull } from "lodash";
import { useDisplay } from "vuetify";
import VanillaTilt from "vanilla-tilt";

// Props
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

const showActionBarAlways = isNull(
  localStorage.getItem("settings.showActionBar"),
)
  ? false
  : localStorage.getItem("settings.showActionBar") === "true";

const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";

// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}

const tiltCard = ref<TiltHTMLElement | null>(null);

onMounted(() => {
  if (tiltCard.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCard.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCard.value?.vanillaTilt && props.enable3DTilt) {
    tiltCard.value.vanillaTilt.destroy();
  }
});
</script>

<template>
  <v-hover v-slot="{ isHovering: isOuterHovering, props: hoverProps }">
    <div data-tilt ref="tiltCard">
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
              :lazy-src="
                romsStore.isSimpleRom(rom)
                  ? rom.path_cover_small?.replace('.png', '.webp') ||
                    fallbackCoverImage
                  : fallbackCoverImage
              "
              :src="
                romsStore.isSimpleRom(rom)
                  ? rom.path_cover_large?.replace('.png', '.webp') ||
                    fallbackCoverImage
                  : rom.igdb_url_cover ||
                    rom.moby_url_cover ||
                    rom.ss_url_cover ||
                    fallbackCoverImage
              "
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
                        !rom.ss_url_cover)
                    "
                    class="translucent-dark text-white"
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
                      :fs-slug="rom.platform_slug"
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
                      class="translucent-dark text-white mr-1 mb-1 px-1"
                      density="compact"
                      title="Verified with Hasheous"
                    >
                      <v-icon>mdi-check-decagram-outline</v-icon>
                    </v-chip>
                    <v-chip
                      v-if="rom.siblings.length > 0 && showSiblings"
                      class="translucent-dark text-white mr-1 mb-1 px-1"
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
                      class="translucent-dark text-white mr-1 mb-1 px-1"
                    >
                      <v-icon>mdi-star</v-icon>
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
                    class="translucent-dark"
                    @menu-open="handleOpenMenu"
                    @menu-close="handleCloseMenu"
                    :rom="rom"
                    :sizeActionBar="sizeActionBar"
                  />
                </v-expand-transition>
              </div>
              <template #error>
                <v-img
                  :lazy-src="
                    romsStore.isSimpleRom(rom)
                      ? rom.path_cover_small || fallbackCoverImage
                      : fallbackCoverImage
                  "
                  :src="
                    romsStore.isSimpleRom(rom)
                      ? rom.path_cover_large || fallbackCoverImage
                      : rom.igdb_url_cover ||
                        rom.moby_url_cover ||
                        rom.ss_url_cover ||
                        fallbackCoverImage
                  "
                >
                  <template #error>
                    <v-img :src="fallbackCoverImage" />
                  </template>
                </v-img>
              </template>
              <template #placeholder>
                <div class="d-flex align-center justify-center fill-height">
                  <v-progress-circular
                    :width="2"
                    :size="40"
                    color="primary"
                    indeterminate
                  />
                </div>
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
</style>
