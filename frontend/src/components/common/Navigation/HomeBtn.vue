<script setup lang="ts">
import RIsotipo from "@/components/common/RIsotipo.vue";
import storeNavigation from "@/stores/navigation";
import { ROUTES } from "@/plugins/router";

const navigationStore = storeNavigation();
</script>
<template>
  <r-isotipo
    :to="{ name: ROUTES.HOME }"
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
  filter: drop-shadow(0px 0px 2px rgba(var(--v-theme-primary)));
}
</style>
