<script setup>
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";

const props = defineProps(["rom"]);
</script>
<template>
  <div class="text-white">
    <v-row no-gutters>
      <span class="text-h4 font-weight-bold title">{{ rom.r_name }}</span>
      <v-chip-group class="ml-3 mt-1 hidden-xs">
        <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{
          rom.region
        }}</v-chip>
        <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{
          rom.revision
        }}</v-chip>
      </v-chip-group>
    </v-row>
    <v-row no-gutters class="align-center">
      <v-chip
        class="font-italic mt-1 title py-5 px-3"
        :to="`/platform/${rom.p_slug}`"
        >{{ rom.p_name || rom.p_slug
        }}<v-avatar :rounded="0" size="43" class="ml-2 pa-1">
          <platform-icon :platform="rom.p_slug"></platform-icon></v-avatar
      ></v-chip>
      <v-chip-group class="ml-3 mt-1 hidden-sm-and-up">
        <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>{{
          rom.region
        }}</v-chip>
        <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>{{
          rom.revision
        }}</v-chip>
      </v-chip-group>
    </v-row>
  </div>
</template>

<style scoped>
.title {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
