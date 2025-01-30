<script setup lang="ts">
import RFooter from "@/components/Settings/Footer.vue";
import { useDisplay } from "vuetify";

const { smAndDown } = useDisplay();
</script>

<template>
  <router-view />
  <r-footer :class="{ desktop: !smAndDown }" />
</template>
<style scoped>
.desktop {
  margin-left: 60px !important;
  width: calc(100% - 60px) !important;
}
</style>
