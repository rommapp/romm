<script setup lang="ts">
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();
const isShowUnmatched = ref(false);
function showUnmatched() {
  isShowUnmatched.value = !isShowUnmatched.value;
  if (isShowUnmatched.value) {
    romsStore.setFilteredUnmatched();
  } else {
    emitter?.emit("filter", null);
  }
}
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Filter unmatched games"
    open-delay="1000"
    ><template v-slot:activator="{ props }">
      <v-btn
        rounded="0"
        variant="text"
        class="ml-0"
        :color="isShowUnmatched ? 'romm-accent-1' : ''"
        icon="mdi-file-find-outline"
        v-bind="props"
        @click="showUnmatched" /></template
  ></v-tooltip>
</template>
<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
