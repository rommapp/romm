<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import GameCardFlags from "@/components/common/Game/Card/Flags.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import storePlatforms from "@/stores/platforms";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
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
    showFlags?: boolean;
    pointerOnHover?: boolean;
    titleOnFooter?: boolean;
    showActionBar?: boolean;
    sizeActionBar?: number;
    showPlatformIcon?: boolean;
    showFav?: boolean;
    withBorderPrimary?: boolean;
    withLink?: boolean;
    disableViewTransition?: boolean;
    enable3DTilt?: boolean;
    src?: string;
  }>(),
  {
    aspectRatio: undefined,
    width: undefined,
    height: undefined,
    transformScale: false,
    titleOnHover: false,
    showFlags: false,
    pointerOnHover: false,
    titleOnFooter: false,
    showActionBar: false,
    sizeActionBar: 0,
    showPlatformIcon: false,
    showFav: false,
    withBorderPrimary: false,
    disableViewTransition: false,
    enable3DTilt: false,
    withLink: false,
    src: "",
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
          <v-hover v-slot="{ isHovering, props: hoverProps }" open-delay="800">
            <v-img
              @click="handleClick"
              @touchstart="handleTouchStart"
              @touchend="handleTouchEnd"
              v-bind="hoverProps"
              cover
              :class="{ pointer: pointerOnHover }"
              :key="romsStore.isSimpleRom(rom) ? rom.updated_at : ''"
              :src="
                src ||
                (romsStore.isSimpleRom(rom)
                  ? rom.path_cover_large || fallbackCoverImage
                  : rom.igdb_url_cover ||
                    rom.moby_url_cover ||
                    rom.ss_url_cover ||
                    fallbackCoverImage)
              "
              :lazy-src="
                src ||
                (romsStore.isSimpleRom(rom)
                  ? rom.path_cover_small || fallbackCoverImage
                  : rom.igdb_url_cover ||
                    rom.moby_url_cover ||
                    rom.ss_url_cover ||
                    fallbackCoverImage)
              "
              :aspect-ratio="computedAspectRatio"
            >
              <div
                v-bind="props"
                style="position: absolute; top: 0; width: 100%"
              >
                <template v-if="titleOnHover">
                  <v-expand-transition>
                    <div
                      v-if="
                        isHovering ||
                        (romsStore.isSimpleRom(rom) &&
                          rom.is_unidentified &&
                          !rom.path_cover_large) ||
                        (!romsStore.isSimpleRom(rom) &&
                          !rom.igdb_url_cover &&
                          !rom.moby_url_cover &&
                          !rom.ss_url_cover)
                      "
                      class="translucent-dark text-white"
                      :class="
                        sizeActionBar === 1 ? 'text-subtitle-1' : 'text-caption'
                      "
                    >
                      <div :class="{ 'pa-2': sizeActionBar === 1 }">
                        <v-list-item>{{ rom.name }}</v-list-item>
                      </div>
                    </div>
                  </v-expand-transition>
                </template>
                <sources v-if="!romsStore.isSimpleRom(rom)" :rom="rom" />
                <v-row no-gutters class="text-white px-1">
                  <game-card-flags
                    v-if="romsStore.isSimpleRom(rom) && showFlags"
                    :rom="rom"
                  />
                  <slot name="prepend-inner"></slot>
                </v-row>
              </div>
              <div class="position-absolute append-inner-left">
                <platform-icon
                  v-if="romsStore.isSimpleRom(rom) && showPlatformIcon"
                  :size="25"
                  :key="rom.platform_slug"
                  :slug="rom.platform_slug"
                  :name="rom.platform_name"
                  :fs-slug="rom.platform_slug"
                  class="label-platform"
                />
              </div>
              <div class="position-absolute append-inner-right">
                <v-btn
                  v-if="
                    romsStore.isSimpleRom(rom) &&
                    collectionsStore.isFav(rom) &&
                    showFav
                  "
                  tabindex="-1"
                  class="label-fav"
                  rouded="0"
                  size="small"
                  color="primary"
                >
                  <v-icon class="icon-fav" size="x-small"
                    >{{
                      collectionsStore.isFav(rom)
                        ? "mdi-star"
                        : "mdi-star-outline"
                    }}
                  </v-icon>
                </v-btn>
              </div>
              <div
                class="position-absolute append-inner-left"
                v-if="!showPlatformIcon"
              >
                <slot name="append-inner-left"></slot>
              </div>
              <div class="position-absolute append-inner-right" v-if="!showFav">
                <slot name="append-inner-right"> </slot>
              </div>
              <template #error>
                <v-img
                  :src="fallbackCoverImage"
                  cover
                  :aspect-ratio="computedAspectRatio"
                ></v-img>
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
              <v-expand-transition>
                <action-bar
                  v-if="
                    showActionBar &&
                    !showActionBarAlways &&
                    (isOuterHovering || activeMenu) &&
                    romsStore.isSimpleRom(rom) &&
                    !smAndDown
                  "
                  class="position-absolute append-inner translucent-dark"
                  @menu-open="handleOpenMenu"
                  @menu-close="handleCloseMenu"
                  :rom="rom"
                  :sizeActionBar="sizeActionBar"
                />
              </v-expand-transition>
            </v-img>
          </v-hover>
          <v-row v-if="titleOnFooter" class="pa-1 align-center">
            <v-col class="pa-0 ml-1 text-truncate">
              <span>{{ rom.name }}</span>
            </v-col>
          </v-row>
        </v-card-text>
        <slot name="footer"></slot>
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
.append-inner {
  bottom: 0rem;
  left: 0rem;
  right: 0rem;
}
.append-inner-left {
  bottom: 0rem;
  left: 0rem;
}
.label-platform {
  right: -0.1rem;
  top: -0.1rem;
}
.append-inner-right {
  bottom: 0rem;
  right: 0rem;
}
.label-fav {
  left: 1.5rem;
  top: 0.5rem;
  transform: rotate(-45deg);
}
.icon-fav {
  transform: rotate(45deg);
  right: 0.25rem;
  bottom: 0.35rem;
}
</style>
