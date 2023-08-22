<script setup>
import { inject } from "vue";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";

// Event listeners bus
const emitter = inject("emitter");

// Props
const props = defineProps(["filteredRoms"]);
const auth = storeAuth();
const romsStore = storeRoms();

// Functions
function selectAllRoms() {
  if (props.filteredRoms.length === romsStore.selected.length) {
    romsStore.reset();
    emitter.emit("openFabMenu", false);
  } else {
    romsStore.updateSelectedRoms(props.filteredRoms);
  }
  emitter.emit("refreshSelected");
}
</script>

<template>
  <v-btn
    color="terciary"
    elevation="8"
    :icon="
      filteredRoms.length === romsStore.selected.length
        ? 'mdi-select'
        : 'mdi-select-all'
    "
    size="large"
    class="mb-2"
    @click.stop="selectAllRoms"
  />

  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    color="terciary"
    elevation="8"
    icon
    size="large"
    class="mb-2"
    @click=""
    ><v-icon>mdi-magnify-scan</v-icon></v-btn
  >

  <v-btn color="terciary" elevation="8" icon size="large" class="mb-2" @click=""
    ><v-icon>mdi-download</v-icon></v-btn
  >

  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    color="terciary"
    elevation="8"
    icon
    size="large"
    class="mb-3"
    @click="emitter.emit('showDeleteRomDialog', romsStore.selected)"
    ><v-icon color="romm-red">mdi-delete</v-icon></v-btn
  >
</template>
