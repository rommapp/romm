<script setup lang="ts">
import RailBtn from "@/components/Drawer/RailBtn.vue";

defineProps<{ rail: boolean }>();
</script>
<template>
  <v-list-item :class="{ 'ml-1': !rail, 'ml-0': rail }" class="my-2">
    <template #prepend>
      <router-link :to="{ name: 'dashboard' }">
        <v-avatar :rounded="0" :size="rail ? 40 : 60"
          ><v-img src="/assets/isotipo.svg"
        /></v-avatar>
        <v-avatar v-if="!rail" :rounded="0" size="60" class="ml-3 mt-1"
          ><v-img src="/assets/logotipo.svg"
        /></v-avatar>
      </router-link>
    </template>
    <template v-if="!rail" #append>
      <rail-btn :rail="rail" />
    </template>
  </v-list-item>
  <v-list-item class="pa-0" v-if="rail">
    <rail-btn :rail="rail" />
  </v-list-item>
</template>

<style scoped>
.home-btn {
  width: 75px;
  cursor: pointer;
}
</style>
