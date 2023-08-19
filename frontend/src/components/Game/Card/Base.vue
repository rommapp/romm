<script setup>
import ActionBar from "@/components/Game/Card/ActionBar.vue";
import Cover from "@/components/Game/Card/Cover.vue";

// Props
const props = defineProps(["rom"]);
</script>

<template>
  <v-hover v-slot="{ isHovering, props }">
    <v-item v-slot="{ isSelected, toggle }">
      <v-card
        v-bind="props"
        class="rom-card"
        :class="{ 'on-hover': isHovering, 'rom-selected': isSelected }"
        :elevation="isHovering ? 20 : 3"
        @click="toggle"
      >
        <v-hover v-slot="{ isHovering, props }" open-delay="800">
          <v-icon style="bottom: 3.1rem; right: 0.6rem" class="position-absolute checkbox" :class="{ 'checkbox-selected': isSelected }" >{{ isSelected ? 'mdi-circle-slice-8' : 'mdi-circle-outline' }}</v-icon>
          <cover :rom="rom" :isHovering="isHovering" :hoverProps="props" />
          <action-bar :rom="rom" />
        </v-hover>
      </v-card>
    </v-item>
  </v-hover>
</template>

<style scoped lang="scss">
.checkbox{
  z-index: 1000 !important;
}
.checkbox.checkbox-selected{
  bottom: 2.9rem !important;
  right: 0.4rem !important;
}
.v-card.on-hover {
  opacity: 1;
}
.v-card:not(.on-hover) {
  opacity: 0.85;
}

.rom-card.rom-selected {
  border: 3px solid rgba(var(--v-theme-romm-accent-2));
  padding: 0;
}

.rom-card:not(.rom-selected) {
  padding: 3px;
}
</style>
