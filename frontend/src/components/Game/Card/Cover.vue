<script setup>
import storeDownload from "@/stores/download";
import storeRoms from "@/stores/roms";

const downloadStore = storeDownload();
const romsStore = storeRoms();

// Props
const props = defineProps(["rom", "isHoveringTop", "size", "selected"]);
const emit = defineEmits(["selectRom"]);

// Functions
function selectRom(event) {
  if (!event.ctrlKey && !event.shiftKey) {
    event.preventDefault();
    emit("selectRom", event);
  }
}

function onNavigate(event) {
  if (event.ctrlKey || event.shiftKey) {
    event.preventDefault();
    event.stopPropagation();
    emit("selectRom", event);
  }
}
</script>

<template>
  <router-link
    style="text-decoration: none; color: inherit"
    :to="
      romsStore.length > 0
        ? `#`
        : `/platform/${$route.params.platform}/${rom.id}`
    "
    @click="onNavigate"
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
        class="cover"
        cover
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
            <v-list-item>{{ rom.file_name }}</v-list-item>
          </div>
        </v-expand-transition>
        <v-chip-group class="pl-1 pt-0">
          <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>
            {{ rom.region }}
          </v-chip>
          <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>
            {{ rom.revision }}
          </v-chip>
        </v-chip-group>
        <v-icon
          v-show="isHoveringTop"
          @click="selectRom"
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
</style>
