<script setup lang="ts">
import { ref } from "vue";
import storeDownload from "@/stores/download";
import storeRoms, { type Rom } from "@/stores/roms";
import { regionToEmoji, languageToEmoji } from "@/utils";

defineProps<{
  rom: Rom;
  isHoveringTop: boolean;
  showSelector: boolean;
  selected: boolean;
}>();
const emit = defineEmits(["selectRom"]);
const downloadStore = storeDownload();
const romsStore = storeRoms();
const card = ref();

let timeout: ReturnType<typeof setTimeout>;

// Functions
function onSelectRom(event: MouseEvent) {
  if (!event.ctrlKey && !event.shiftKey) {
    event.preventDefault();
    emit("selectRom", event);
  }
}

function onNavigate(event: MouseEvent) {
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

function onTouchStart(event: TouchEvent) {
  card.value.$el.addEventListener("contextmenu", (event: Event) => {
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
        :src="`/assets/romm/resources/${
          rom.path_cover_l || rom.merged_screenshots[0]
        }`"
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
        <v-chip-group class="ml-2 pt-0 text-shadow position-absolute flags">
          <v-chip
            v-if="rom.regions.filter((i: string) => i).length > 0"
            :title="`Regions: ${rom.regions.join(', ')}`"
            class="bg-chip px-2 py-3"
            density="compact"
          >
            <span class="px-1" v-for="region in rom.regions">
              {{ regionToEmoji(region) }}
            </span>
          </v-chip>
          <v-chip
            v-if="rom.languages.filter((i: string) => i).length > 0"
            :title="`Languages: ${rom.languages.join(', ')}`"
            class="bg-chip px-2 py-3"
            density="compact"
          >
            <span class="px-1" v-for="language in rom.languages">
              {{ languageToEmoji(language) }}
            </span>
          </v-chip>
          <v-chip
            v-if="rom.siblings && rom.siblings.length > 0"
            :title="`${rom.siblings.length + 1} versions`"
            class="bg-chip px-2 py-3"
            density="compact"
          >
            +{{ rom.siblings.length }}
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
.flags {
  bottom: -0.25rem;
  left: 0;
}
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
