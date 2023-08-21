<script setup>
import { ref } from "vue";
import useRomsStore from "@/stores/roms.js";
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import Cover from "@/components/Game/Card/Cover.vue";

// Props
const props = defineProps(["rom"]);
const romsStore = useRomsStore();
const selected = ref(romsStore.selected.includes(props.rom.id));
function selectRom() {
  selected.value = !selected.value;
}
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      class="rom-card"
      :class="{ 'on-hover': isHovering, 'rom-selected': selected }"
      :elevation="isHovering ? 20 : 3"
    >
      <v-hover v-slot="{ isHovering, props }" open-delay="800">
        
        <cover :rom="rom" :isHovering="isHovering" :hoverProps="props" :selected="selected" @selectRom="selectRom()"/>
        <action-bar :rom="rom" />
      </v-hover>
    </v-card>
  </v-hover>
</template>

<style scoped lang="scss">
.v-card {
  opacity: 0.85;
  border: 3px solid rgba(var(--v-theme-primary));
}
.v-card.on-hover {
  opacity: 1;
}
.v-card.rom-selected {
  border: 3px solid rgba(var(--v-theme-romm-accent-2));
}
</style>
