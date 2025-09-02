<script setup lang="ts">
import RIsotipo from "@/components/common/RIsotipo.vue";
import { ROUTES } from "@/plugins/router";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

const { smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { mainBarCollapsed } = storeToRefs(navigationStore);
</script>

<template>
  <router-link :to="{ name: ROUTES.HOME }" class="cursor-pointer">
    <r-isotipo :size="smAndDown ? 35 : 40" :avatar="mainBarCollapsed" />
  </router-link>
</template>
