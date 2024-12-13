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
        :color="romsStore.selecting ? 'romm-accent-1' : ''"
        rounded="0"
        variant="text"
        v-bind="props"
        class="mr-0"
        icon="mdi-select-group"
        @click="romsStore.isSelecting()" /></template
  ></v-tooltip>
</template>
