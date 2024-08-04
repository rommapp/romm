<script setup lang="ts">
import { ref } from "vue";
import RommIso from "@/components/common/RommIso.vue";
import storeNavigation from "@/stores/navigation";

const homeUrl = ref(`${location.protocol}//${location.host}`);
const navigationStore = storeNavigation();
</script>
<template>
  <a @click.prevent style="text-decoration: none; color: inherit" :href="homeUrl">
    <v-hover v-slot="{ isHovering, props: hoverProps }">
      <romm-iso
        @click="navigationStore.goHome"
        v-bind="hoverProps"
        class="pointer"
        :class="{ 'border-romm-accent-1': isHovering }"
        :size="35"
      />
    </v-hover>
  </a>
</template>
