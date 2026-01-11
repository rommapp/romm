<script setup lang="ts">
import { computed, ref } from "vue";
import type { Walkthrough } from "@/composables/useWalkthrough";
import type { DetailedRom } from "@/stores/roms";
import WalkthroughContent from "./WalkthroughContent.vue";
import WalkthroughHeader from "./WalkthroughHeader.vue";

const props = defineProps<{
  rom: DetailedRom;
}>();

const walkthroughs = computed<Walkthrough[]>(
  () => (props.rom.walkthroughs || []) as Walkthrough[],
);

const openPanels = ref<number[]>([]);

const isOpen = (id: number) => openPanels.value.includes(id);
</script>

<template>
  <v-alert
    v-if="!walkthroughs.length"
    type="info"
    variant="tonal"
    text="No walkthroughs saved for this ROM."
  />
  <v-expansion-panels v-else v-model="openPanels" multiple>
    <v-expansion-panel
      v-for="wt in walkthroughs"
      :key="wt.id"
      :value="wt.id"
      elevation="0"
    >
      <WalkthroughHeader :walkthrough="wt" />
      <WalkthroughContent :walkthrough="wt" :is-open="isOpen" />
    </v-expansion-panel>
  </v-expansion-panels>
</template>
