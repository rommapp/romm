<script setup>
import { ref, inject } from "vue";
import useRomsStore from "@/stores/roms.js";
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import Cover from "@/components/Game/Card/Cover.vue";

// Props
const props = defineProps(["rom", "index"]);
const emit = defineEmits(["selectRom"]);
const romsStore = useRomsStore();
const selected = ref();

// Functions
function selectRom(event) {
  selected.value = !selected.value;
  if (selected.value) {
    romsStore.addSelectedRoms(props.rom);
  } else {
    romsStore.removeSelectedRoms(props.rom);
  }
  emit("selectRom", { event, index: props.index, selected: selected.value });
}

const emitter = inject("emitter");
emitter.on("refreshSelected", () => {
  selected.value = romsStore.selected
    .map((rom) => rom.id)
    .includes(props.rom.id);
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-card
      v-bind="props"
      class="rom-card"
      :class="{ 'on-hover': isHovering, 'rom-selected': selected }"
      :elevation="isHovering ? 20 : 3"
    >
      <cover
        :rom="rom"
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
