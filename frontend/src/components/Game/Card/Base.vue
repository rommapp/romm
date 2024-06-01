<script setup lang="ts">
import storeDownload from "@/stores/download";
import storeRoms, { type SimpleRom } from "@/stores/roms.js";
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import { storeToRefs } from "pinia";
import { onMounted, onUnmounted, ref } from "vue";
import storeGalleryView from "@/stores/galleryView";
import { useTheme } from "vuetify";

// Props
const props = withDefaults(
  defineProps<{
    rom: SimpleRom;
    index?: number | null;
    transformScale?: boolean;
    titleOnHover?: boolean;
    titleOnFooter?: boolean;
    showActionBar?: boolean;
    detailsOnClick?: boolean;
    withBorder?: boolean;
    src?: string;
  }>(),
  {
    index: null,
    transformScale: false,
    titleOnHover: false,
    titleOnFooter: false,
    showActionBar: false,
    detailsOnClick: true,
    withBorder: false,
    src: "",
  }
);
const emit = defineEmits(["selectRom"]);
const romsStore = storeRoms();
const downloadStore = storeDownload();
const { selectedRoms } = storeToRefs(romsStore);
const card = ref();
let timeout: ReturnType<typeof setTimeout>;
const theme = useTheme();
const galleryViewStore = storeGalleryView();

// Functions
function selectRom(event: MouseEvent) {
  if (!selectedRoms.value.includes(props.rom)) {
    romsStore.addToSelection(props.rom);
  } else {
    romsStore.removeFromSelection(props.rom);
  }
  emit("selectRom", {
    event,
    selected: !selectedRoms.value.includes(props.rom),
  });
}

function onNavigate(event: MouseEvent) {
  if (
    event.ctrlKey ||
    event.shiftKey ||
    romsStore.selecting ||
    romsStore.selectedRoms.length > 0
  ) {
    event.preventDefault();
    event.stopPropagation();
    emit("selectRom", event);
  }
}

function onTouchStart(event: TouchEvent) {
  card.value.$el.addEventListener("contextmenu", (event: Event) => {
    event.preventDefault();
  });
  timeout = setTimeout(() => {
    emit("selectRom", event);
  }, 500);
}

function onTouchEnd() {
  clearTimeout(timeout);
}

function onScroll() {
  clearTimeout(timeout);
}

onMounted(() => {
  window.addEventListener("scroll", onScroll);
});

onUnmounted(() => {
  window.removeEventListener("scroll", onScroll);
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      :class="{
        'on-hover': isHovering,
        selected: selectedRoms?.includes(rom),
        'transform-scale': transformScale,
        'with-border': withBorder,
      }"
      :elevation="isHovering && transformScale ? 20 : 2"
    >
      <v-progress-linear
        color="romm-accent-1"
        :active="downloadStore.value.includes(rom.id)"
        :indeterminate="true"
        absolute
      />
      <router-link
        style="text-decoration: none; color: inherit"
        :to="
          romsStore.selecting ||
          romsStore.selectedRoms.length > 0 ||
          !detailsOnClick
            ? {}
            : {
                name: 'rom',
                params: { rom: rom.id },
              }
        "
        ref="card"
        @click="onNavigate"
        @touchstart="onTouchStart"
        @touchend="onTouchEnd"
      >
        <v-hover v-slot="{ isHovering, props }" open-delay="800">
          <v-img
            v-bind="props"
            :src="
              src
                ? src
                : !rom.igdb_id && !rom.moby_id && !rom.has_cover
                ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                : `/assets/romm/resources/${rom.path_cover_l}`
            "
            :lazy-src="
              !rom.igdb_id && !rom.moby_id
                ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                : rom.has_cover
                ? `/assets/romm/resources/${rom.path_cover_s}`
                : `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
            "
            :aspect-ratio="3 / 4"
          >
            <div v-bind="props" style="position: absolute; top: 0; width: 100%">
              <template v-if="titleOnHover">
                <v-expand-transition>
                  <div
                    v-if="isHovering || !rom.has_cover"
                    class="translucent text-caption"
                    :class="{
                      'text-truncate':
                        galleryViewStore.current == 0 && !isHovering,
                    }"
                  >
                    <v-list-item>{{ rom.name }}</v-list-item>
                  </div>
                </v-expand-transition>
              </template>

              <slot name="prepend-inner"></slot>
            </div>
            <slot name="append-inner"></slot>
            <template v-slot:error>
              <v-img
                :src="`/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`"
                :aspect-ratio="3 / 4"
              ></v-img>
            </template>
            <template v-slot:placeholder>
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
      </router-link>
      <v-card-text v-if="titleOnFooter">
        <v-row class="pa-1 align-center">
          <v-col class="pa-0 ml-1 text-truncate">
            <span>{{ rom.name }}</span>
          </v-col>
        </v-row>
      </v-card-text>
      <slot name="footer"></slot>
      <action-bar v-if="showActionBar" :rom="rom" />
    </v-card>
  </v-hover>
</template>

<style scoped>
.v-card.with-border {
  border: 3px solid rgba(var(--v-theme-primary));
}
.v-card.selected {
  border: 3px solid rgba(var(--v-theme-romm-accent-1));
  transform: scale(1.03);
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
</style>
