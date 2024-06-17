<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import Sources from "@/components/Game/Card/Sources.vue";
import storeDownload from "@/stores/download";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms.js";
import { storeToRefs } from "pinia";
import { onMounted, ref } from "vue";
import { useTheme } from "vuetify";

// Type guard function to check if rom is of type SimpleRom or SearchRomSchema
function isSimpleRom(rom: SimpleRom | SearchRomSchema): rom is SimpleRom {
  return (rom as SimpleRom).id !== undefined;
}

// Props
const props = withDefaults(
  defineProps<{
    rom: SimpleRom | SearchRomSchema;
    transformScale?: boolean;
    titleOnHover?: boolean;
    titleOnFooter?: boolean;
    showActionBar?: boolean;
    withBorder?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    titleOnHover: false,
    titleOnFooter: false,
    showActionBar: false,
    withBorder: false,
    src: "",
  }
);
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
const romsStore = storeRoms();
const downloadStore = storeDownload();
const { selectedRoms } = storeToRefs(romsStore);
const card = ref();
const theme = useTheme();
const galleryViewStore = storeGalleryView();

// Functions
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
        'border-romm-accent-1':
          isSimpleRom(rom) && selectedRoms?.includes(rom),
        'transform-scale': transformScale,
        'with-border': withBorder,
      }"
      :elevation="isHovering && transformScale ? 20 : 2"
    >
      <v-progress-linear
        v-if="isSimpleRom(rom)"
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
          class="pointer"
          ref="card"
          :src="
            src
              ? src
              : isSimpleRom(rom)
              ? !rom.igdb_id && !rom.moby_id
                ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                : !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                : `/assets/romm/resources/${rom.path_cover_l}`
              : !rom.igdb_url_cover && !rom.moby_url_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : rom.igdb_url_cover
              ? rom.igdb_url_cover
              : rom.moby_url_cover
          "
          :lazy-src="
            isSimpleRom(rom)
              ? !rom.igdb_id && !rom.moby_id
                ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                : !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                : `/assets/romm/resources/${rom.path_cover_s}`
              : !rom.igdb_url_cover && !rom.moby_url_cover
              ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
              : rom.igdb_url_cover
              ? rom.igdb_url_cover
              : rom.moby_url_cover
          "
          :aspect-ratio="3 / 4"
        >
          <div v-bind="props" style="position: absolute; top: 0; width: 100%">
            <template v-if="titleOnHover">
              <v-expand-transition>
                <div
                  v-if="
                    isHovering ||
                    (isSimpleRom(rom) && !rom.has_cover) ||
                    (!isSimpleRom(rom) &&
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
            <sources v-if="!isSimpleRom(rom)" :rom="rom" />
            <slot name="prepend-inner"></slot>
          </div>
          <div class="position-absolute append-inner">
            <slot name="append-inner"></slot>
          </div>

          <template #error>
            <v-img
              :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
              :aspect-ratio="3 / 4"
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
      <action-bar v-if="showActionBar && isSimpleRom(rom)" :rom="rom" />
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
.append-inner {
  bottom: -0.1rem;
  right: -0.3rem;
}
</style>
