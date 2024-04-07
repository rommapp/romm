<script setup lang="ts">
import storeDownload from "@/stores/download";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type Rom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { identity, isNull } from "lodash";
import { ref } from "vue";
import { useTheme } from "vuetify";

defineProps<{
  rom: Rom;
  isHoveringTop: boolean;
  showSelector: boolean;
  selected: boolean;
}>();
const theme = useTheme();
const downloadStore = storeDownload();
const galleryViewStore = storeGalleryView();
const romsStore = storeRoms();
const card = ref();
const emit = defineEmits(["selectRom"]);
const showRegions = isNull(localStorage.getItem("settings.showRegions"))
  ? true
  : localStorage.getItem("settings.showRegions") === "true";
const showLanguages = isNull(localStorage.getItem("settings.showLanguages"))
  ? true
  : localStorage.getItem("settings.showLanguages") === "true";
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";

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
        :src="
          !rom.igdb_id && !rom.moby_id && !rom.has_cover
            ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
            : !rom.has_cover
            ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
            : `/assets/romm/resources/${rom.path_cover_l}`
        "
        :lazy-src="
          !rom.igdb_id && !rom.moby_id && !rom.has_cover
            ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
            : !rom.has_cover
            ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
            : `/assets/romm/resources/${rom.path_cover_s}`
        "
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
            class="translucent text-caption"
            :class="{
              'text-truncate': galleryViewStore.current == 0 && !isHovering,
            }"
          >
            
            <v-list-item>{{ rom.name }}</v-list-item>
          </div>
        </v-expand-transition>
        <v-row no-gutters class="text-white px-1">
          <v-chip
            v-if="rom.regions.filter(identity).length > 0 && showRegions"
            :title="`Regions: ${rom.regions.join(', ')}`"
            class="translucent mr-1 mt-1 px-1"
            :class="{ 'emoji-collection': rom.regions.length > 3 }"
            density="compact"
          >
            <span class="emoji" v-for="region in rom.regions.slice(0, 3)">
              {{ regionToEmoji(region) }}
            </span>
          </v-chip>
          <v-chip
            v-if="rom.languages.filter(identity).length > 0 && showLanguages"
            :title="`Languages: ${rom.languages.join(', ')}`"
            class="translucent mr-1 mt-1 px-1"
            :class="{ 'emoji-collection': rom.languages.length > 3 }"
            density="compact"
          >
            <span class="emoji" v-for="language in rom.languages.slice(0, 3)">
              {{ languageToEmoji(language) }}
            </span>
          </v-chip>
          <v-chip
            v-if="rom.siblings && rom.siblings.length > 0 && showSiblings"
            :title="`${rom.siblings.length + 1} versions`"
            class="translucent mr-1 mt-1"
            density="compact"
          >
            +{{ rom.siblings.length }}
          </v-chip>
        </v-row>
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
.checkbox {
  bottom: 0.2rem;
  right: 0.2rem;
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
}

.emoji-collection {
  mask-image: linear-gradient(to right, black 0%, black 70%, transparent 100%);
}

.emoji {
  margin: 0 2px;
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
