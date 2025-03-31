<script setup lang="ts">
import { ROUTES } from "@/plugins/router";
import { useDisplay } from "vuetify";
import RIsotipo from "@/components/common/RIsotipo.vue";

// Props
const { smAndDown } = useDisplay();
</script>
<template>
  <router-link :to="{ name: ROUTES.HOME }" class="cursor-pointer">
    <r-isotipo :size="smAndDown ? 35 : 40" />
  </router-link>
</template>
