<script setup lang="ts">
import { ref } from "vue";
import RIsotipo from "@/components/common/RIsotipo.vue";
import storeNavigation from "@/stores/navigation";

const homeUrl = ref(`${location.protocol}//${location.host}`);
const navigationStore = storeNavigation();
</script>
<template>
  <r-isotipo
    :to="homeUrl"
    @click="navigationStore.goHome"
    class="cursor-pointer"
    :size="40"
  />
</template>

<style scoped>
.v-avatar {
  transition: filter 0.15s ease-in-out;
}
.v-avatar:hover,
.v-avatar.active {
  filter: drop-shadow(0px 0px 2px rgba(var(--v-theme-romm-accent-1)));
}
</style>
