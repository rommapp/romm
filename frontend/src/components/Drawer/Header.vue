<script setup lang="ts">
import RailBtn from "@/components/Drawer/RailBtn.vue";
import RommIso from "@/components/common/RommIso.vue";
import RommLogo from "@/components/common/RommLogo.vue";

defineProps<{ rail: boolean }>();
</script>
<template>
  <v-list-item :class="{ 'ml-1': !rail, 'ml-0': rail }" class="my-2">
    <template #prepend>
      <router-link :to="{ name: 'dashboard' }">
        <romm-iso :size="rail ? 40 : 60" />
        <romm-logo v-if="!rail" :size="60" class="ml-3 mt-1" />
      </router-link>
    </template>
    <template v-if="!rail" #append>
      <rail-btn :rail="rail" class="ml-1" />
    </template>
  </v-list-item>
  <v-list-item v-if="rail" class="pa-0">
    <rail-btn :rail="rail" />
  </v-list-item>
</template>
