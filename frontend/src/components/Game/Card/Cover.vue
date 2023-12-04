<script setup>
import { ref } from "vue";
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";
import { regionToEmoji, languageToEmoji } from "@/utils/utils";

// Props
const props = defineProps([
  "rom",
  "isHoveringTop",
  "showSelector",
  "size",
  "selected",
]);
const emit = defineEmits(["selectRom"]);
const downloadStore = storeDownload();
const romsStore = storeRoms();
const card = ref();
let timeout;

// Functions
function onSelectRom(event) {
  if (!event.ctrlKey && !event.shiftKey) {
    event.preventDefault();
    emit("selectRom", event);
  }
}

function onNavigate(event) {
  if (
    event.ctrlKey ||
    event.shiftKey ||
    (romsStore.touchScreen && romsStore.selectedRoms.length > 0)
  ) {
    event.preventDefault();
    event.stopPropagation();
    emit("selectRom", event);
  }
}

function onTouchStart(event) {
  card.value.$el.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });
  romsStore.isTouchScreen(true);
  timeout = setTimeout(() => {
    emit("selectRom", event);
  }, 500);
}

function onTouchEnd() {
  clearTimeout(timeout);
}
</script>

<template>
  <router-link
    style="text-decoration: none; color: inherit"
    :to="
      romsStore.touchScreen && romsStore.selectedRoms.length > 0
        ? ''
        : `/platform/${rom.platform_slug}/${rom.id}`
    "
    ref="card"
    @click="onNavigate"
    @touchstart="onTouchStart"
    @touchend="onTouchEnd"
  >
    <v-progress-linear
      color="romm-accent-1"
      :active="downloadStore.value.includes(rom.id)"
      :indeterminate="true"
      absolute
    />
    <v-hover v-slot="{ isHovering, props }" open-delay="800">
      <v-img
        :value="rom.id"
        :key="rom.id"
        v-bind="props"
        :src="`/assets/romm/resources/${rom.path_cover_l}`"
        :lazy-src="`/assets/romm/resources/${rom.path_cover_s}`"
        :aspect-ratio="3 / 4"
      >
        <template v-slot:placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular
              color="romm-accent-1"
              :width="2"
              indeterminate
            />
          </div>
        </template>
        <v-expand-transition>
          <div
            v-if="isHovering || !rom.has_cover"
            class="rom-title d-flex transition-fast-in-fast-out bg-tooltip text-caption"
          >
            <v-list-item>{{ rom.name || rom.file_name }}</v-list-item>
          </div>
        </v-expand-transition>
        <v-chip-group class="pl-1 pt-0 text-black position-absolute chips">
          <v-chip
            v-if="rom.regions.length > 0"
            :title="`Regions: ${rom.regions.join(', ')}`"
            size="large"
            class="pr-2 pl-2 bg-chip"
            density="compact"
            label
          >
            <span v-for="region in rom.regions">
              {{ regionToEmoji(region) }}&nbsp;
            </span>
          </v-chip>
          <v-chip
            v-if="rom.languages.length > 0"
            :title="`Languages: ${rom.languages.join(', ')}`"
            size="large"
            class="pr-2 pl-2 bg-chip"
            density="compact"
            label
          >
            <span v-for="language in rom.languages">
              {{ languageToEmoji(language) }}&nbsp;
            </span>
          </v-chip>
        </v-chip-group>
        <v-icon
          v-show="isHoveringTop && showSelector"
          @click="onSelectRom"
          size="small"
          class="position-absolute checkbox"
          :class="{ 'checkbox-selected': selected }"
          >{{ selected ? "mdi-circle-slice-8" : "mdi-circle-outline" }}</v-icon
        >
      </v-img>
    </v-hover>
  </router-link>
</template>

<style scoped>
.rom-title {
  opacity: 0.85;
}
.rom-title.on-hover {
  opacity: 1;
}
.checkbox {
  bottom: 0.2rem;
  right: 0.2rem;
}

.chips {
  bottom: -0.25rem;
  left: 0;
}
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
