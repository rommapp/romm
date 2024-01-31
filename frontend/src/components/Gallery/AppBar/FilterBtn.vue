<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { ref, inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const isShowFilterBar = ref(false);
function showFilterBar() {
  emitter?.emit('filterBarShow', null)
  isShowFilterBar.value = !isShowFilterBar.value
}
</script>

<template>
  <v-btn
    class="ml-0"
    variant="text"
    rounded="0"
    icon="mdi-filter-variant"
    :color="isShowFilterBar ? 'romm-accent-1' : ''"
    title="Filter gallery"
    @click="showFilterBar"
  />
</template>
