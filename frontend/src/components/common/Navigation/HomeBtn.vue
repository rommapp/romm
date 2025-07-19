<script setup lang="ts">
import { ROUTES } from "@/plugins/router";
import storeNavigation from "@/stores/navigation";
import RIsotipo from "@/components/common/RIsotipo.vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

const { smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { mainBarCollapsed } = storeToRefs(navigationStore);
</script>

<template>
  <router-link :to="{ name: ROUTES.HOME }" class="cursor-pointer">
    <r-isotipo :size="smAndDown ? 35 : 40" :avatar="mainBarCollapsed" />
  </router-link>
</template>
