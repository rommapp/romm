<script setup>
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";

const props = defineProps(["rom"]);
</script>
<template>
  <v-row no-gutters>
    <div class="text-h4 text-white font-weight-bold title text-truncate">
      {{ rom.r_name }}
    </div>
  </v-row>
  <v-row no-gutters class="align-center mt-2">
    <v-chip
      class="font-italic text-white title py-5 px-3"
      :to="`/platform/${rom.p_slug}`"
      >{{ rom.p_name || rom.p_slug
      }}<v-avatar :rounded="0" size="43" class="ml-2 pa-1">
        <platform-icon :platform="rom.p_slug"></platform-icon></v-avatar
    ></v-chip>
    <v-chip-group v-if="rom.region || rom.revision" class="ml-3">
      <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{
        rom.region
      }}</v-chip>
      <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{
        rom.revision
      }}</v-chip>
    </v-chip-group>
  </v-row>
</template>

<style scoped>
.title {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
