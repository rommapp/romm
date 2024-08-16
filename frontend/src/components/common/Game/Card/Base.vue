<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import ActionBar from "@/components/common/Game/Card/ActionBar.vue";
import GameCardFlags from "@/components/common/Game/Card/Flags.vue";
import Sources from "@/components/common/Game/Card/Sources.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import storeCollections from "@/stores/collections";
import storeDownload from "@/stores/download";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import { type SimpleRom } from "@/stores/roms.js";
import { storeToRefs } from "pinia";
import { onMounted, ref } from "vue";
import { useTheme } from "vuetify";

// Props
const props = withDefaults(
  defineProps<{
    rom: SimpleRom | SearchRomSchema;
    transformScale?: boolean;
    titleOnHover?: boolean;
    showFlags?: boolean;
    pointerOnHover?: boolean;
    titleOnFooter?: boolean;
    showActionBar?: boolean;
    showPlatformIcon?: boolean;
    showFav?: boolean;
    withBorder?: boolean;
    withBorderRommAccent?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    titleOnHover: false,
    showFlags: false,
    pointerOnHover: true,
    titleOnFooter: false,
    showActionBar: false,
    showPlatformIcon: false,
    showFav: false,
    withBorder: false,
    withBorderRommAccent: false,
    src: "",
  }
);
const romsStore = storeRoms();
const emit = defineEmits(["click", "touchstart", "touchend"]);
const handleClick = (event: MouseEvent) => {
  emit("click", { event: event, rom: props.rom });
};
const handleTouchStart = (event: TouchEvent) => {
  emit("touchstart", { event: event, rom: props.rom });
};
const handleTouchEnd = (event: TouchEvent) => {
  emit("touchend", { event: event, rom: props.rom });
};
const downloadStore = storeDownload();
const card = ref();
const theme = useTheme();
const galleryViewStore = storeGalleryView();
const collectionsStore = storeCollections();

onMounted(() => {
  card.value.$el.addEventListener("contextmenu", (event: Event) => {
    event.preventDefault();
  });
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-card
      v-bind="hoverProps"
      :class="{
        'on-hover': isHovering,
        'border-romm-accent-1': withBorderRommAccent,
        'transform-scale': transformScale,
        'with-border': withBorder,
      }"
      :elevation="isHovering && transformScale ? 20 : 3"
    >
      <v-progress-linear
        v-if="romsStore.isSimpleRom(rom)"
        color="romm-accent-1"
        :active="downloadStore.value.includes(rom.id)"
        :indeterminate="true"
        absolute
      />
      <v-hover v-slot="{ isHovering, props: hoverProps }" open-delay="800">
        <v-img
          @click="handleClick"
          @touchstart="handleTouchStart"
          @touchend="handleTouchEnd"
          v-bind="hoverProps"
          :class="{ pointer: pointerOnHover }"
          ref="card"
          cover
          :key="romsStore.isSimpleRom(rom) ? rom.updated_at : ''"
          :src="
            src
              ? src
              : romsStore.isSimpleRom(rom)
              ? !rom.igdb_id && !rom.moby_id && !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                : (rom.igdb_id || rom.moby_id) && !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                : `/assets/romm/resources/${rom.path_cover_l}?ts=${rom.updated_at}`
              : !rom.igdb_url_cover && !rom.moby_url_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : rom.igdb_url_cover
              ? rom.igdb_url_cover
              : rom.moby_url_cover
          "
          :lazy-src="
            romsStore.isSimpleRom(rom)
              ? !rom.igdb_id && !rom.moby_id && !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                : (rom.igdb_id || rom.moby_id) && !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                : `/assets/romm/resources/${rom.path_cover_s}?ts=${rom.updated_at}`
              : !rom.igdb_url_cover && !rom.moby_url_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : rom.igdb_url_cover
              ? rom.igdb_url_cover
              : rom.moby_url_cover
          "
          :aspect-ratio="2 / 3"
        >
          <div v-bind="props" style="position: absolute; top: 0; width: 100%">
            <template v-if="titleOnHover">
              <v-expand-transition>
                <div
                  v-if="
                    isHovering ||
                    (romsStore.isSimpleRom(rom) && !rom.has_cover) ||
                    (!romsStore.isSimpleRom(rom) &&
                      !rom.igdb_url_cover &&
                      !rom.moby_url_cover)
                  "
                  class="translucent-dark text-caption text-white"
                  :class="{
                    'text-truncate':
                      galleryViewStore.currentView == 0 && !isHovering,
                  }"
                >
                  <v-list-item>{{ rom.name }}</v-list-item>
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
              @click.stop=""
              class="label-fav"
              rouded="0"
              size="small"
              color="romm-accent-1"
            >
              <v-icon class="icon-fav" size="x-small"
                >{{
                  collectionsStore.isFav(rom) ? "mdi-star" : "mdi-star-outline"
                }}
              </v-icon>
            </v-btn>
          </div>
          <div
            class="position-absolute append-inner-left"
            v-if="!showPlatformIcon"
          >
            <slot name="append-inner-left"> </slot>
          </div>
          <div class="position-absolute append-inner-right" v-if="!showFav">
            <slot name="append-inner-right"> </slot>
          </div>
          <template #error>
            <v-img
              :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
              cover
              :aspect-ratio="2 / 3"
            ></v-img>
          </template>
          <template #placeholder>
            <div class="d-flex align-center justify-center fill-height">
              <v-progress-circular
                :width="2"
                :size="40"
                color="romm-accent-1"
                indeterminate
              />
            </div>
          </template>
        </v-img>
      </v-hover>
      <v-card-text v-if="titleOnFooter">
        <v-row class="pa-1 align-center">
          <v-col class="pa-0 ml-1 text-truncate">
            <span>{{ rom.name }}</span>
          </v-col>
        </v-row>
      </v-card-text>
      <slot name="footer"></slot>
      <action-bar
        v-if="showActionBar && romsStore.isSimpleRom(rom)"
        :rom="rom"
      />
    </v-card>
  </v-hover>
</template>

<style scoped>
.with-border {
  border: 1px solid rgba(var(--v-theme-primary));
}
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
  transition: max-height 0.5s; /* Adjust the transition duration if needed */
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
