<script setup lang="ts">
import storeRoms from "@/stores/roms.js";
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import Cover from "@/components/Game/Card/Cover.vue";

// Props
const props = defineProps(["rom", "index", "selected", "showSelector"]);
const emit = defineEmits(["selectRom"]);
const romsStore = storeRoms();

// Functions
function selectRom(event: MouseEvent) {
  if (!props.selected) {
    romsStore.addToSelection(props.rom);
  } else {
    romsStore.removeFromSelection(props.rom);
  }
  emit("selectRom", { event, index: props.index, selected: !props.selected });
}
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      :class="{ 'on-hover': isHovering, 'rom-selected': selected }"
      :elevation="isHovering ? 20 : 3"
    >
      <cover
        :rom="rom"
        :showSelector="showSelector"
        :isHoveringTop="isHovering"
        :selected="selected"
        @selectRom="selectRom"
      />
      <action-bar :rom="rom" />
    </v-card>
  </v-hover>
</template>

<style scoped lang="scss">
.v-card {
  border: 3px solid rgba(var(--v-theme-primary));
  opacity: 0.85;
  transition-property: all;
  transition-duration: 0.1s;
}
.v-card.rom-selected {
  border: 3px solid rgba(var(--v-theme-romm-accent-1));
  transform: scale(1.03); 
}
.v-card.on-hover {
  z-index: 1 !important;
  opacity: 1;
  transform: scale(1.05); 
}
</style>
