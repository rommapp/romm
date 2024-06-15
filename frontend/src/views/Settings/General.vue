<script setup lang="ts">
import RFooter from "@/components/Settings/Footer.vue";
import Interface from "@/layouts/Settings/General/Interface.vue";
import Tasks from "@/layouts/Settings/General/Tasks.vue";
import Theme from "@/layouts/Settings/General/Theme.vue";
import storeAuth from "@/stores/auth";

// Props
const auth = storeAuth();
</script>
<template>
  <theme />
  <interface />
  <tasks v-if="auth.scopes.includes('tasks.run')" />
  <r-footer />
</template>
