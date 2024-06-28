<script setup lang="ts">
import RommIso from "@/components/common/RommIso.vue";
import storeNavigation from "@/stores/navigation";

const navigationStore = storeNavigation();
</script>
<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <romm-iso
      @click="navigationStore.goHome"
      v-bind="hoverProps"
      class="pointer"
      :class="{ 'border-romm-accent-1': isHovering }"
      :size="35"
    />
  </v-hover>
</template>
