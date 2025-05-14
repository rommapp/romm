<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const romsStore = storeRoms();
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    :text="t('platform.active-multi-select')"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        :color="romsStore.selectingRoms ? 'primary' : ''"
        variant="text"
        rounded="0"
        v-bind="props"
        class="mr-0"
        icon="mdi-select-group"
        aria-label="Multi select"
        @click="romsStore.setSelecting()" /></template
  ></v-tooltip>
</template>
