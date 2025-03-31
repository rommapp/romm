<script setup lang="ts">
import { ROUTES } from "@/plugins/router";

import RIsotipo from "@/components/common/RIsotipo.vue";
</script>
<template>
  <router-link :to="{ name: ROUTES.HOME }" class="cursor-pointer">
    <r-isotipo :size="40" />
  </router-link>
</template>
