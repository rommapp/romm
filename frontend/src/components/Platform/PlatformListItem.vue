<script setup>
// Props
const props = defineProps(["platform", "rail"]);
import PlatformIcon from "./PlatformIcon.vue";
</script>

<template>
  <v-list-item
    :to="`/platform/${platform.slug}`"
    :value="platform.slug"
    :key="platform"
    class="pt-4 pb-4 bg-terciary"
  >
    <span v-if="!rail" class="text-body-2">{{ platform.name }}</span>
    <template v-slot:prepend>
      <v-avatar :rounded="0" size="40">
        <platform-icon :platform="platform"></platform-icon>
      </v-avatar>
    </template>
    <template v-slot:append>
      <v-chip v-if="!rail" class="ml-4 bg-chip" size="x-small" label>{{
        platform.n_roms
      }}</v-chip>
    </template>
  </v-list-item>
</template>
