<script setup lang="ts">
import type { Emitter } from "mitt";
import { ref, inject } from "vue";
import type { Events } from "@/types/emitter";

const emitter = inject<Emitter<Events>>("emitter");
const isShowSortBar = ref(false);
function showSortBar() {
  emitter?.emit("sortBarShow", null);
  isShowSortBar.value = !isShowSortBar.value;
}
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    text="Order gallery"
    transition="fade-transition"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        class="ml-0"
        variant="text"
        rounded="0"
        icon="mdi-sort"
        v-bind="props"
        :color="isShowSortBar ? 'primary' : ''"
        @click="showSortBar"
      />
    </template>
  </v-tooltip>
</template>
