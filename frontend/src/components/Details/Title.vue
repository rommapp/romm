<script setup>
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";

const props = defineProps(["rom"]);
const { xs, sm, md, smAndUp } = useDisplay();
</script>
<template>
  <v-row no-gutters>
    <div class="text-h5 text-white text-shadow font-weight-bold title" :class="{'text-truncate': smAndUp }">
      {{ rom.name }}
    </div>
  </v-row>
  <v-row no-gutters class="align-center mt-2">
    <v-chip
      class="font-italic text-white text-shadow title pa-3"
      :to="`/platform/${rom.platform_slug}`"
    >
    {{ rom.platform_name || rom.platform_slug }}
      <v-avatar :rounded="0" size="43" class="ml-2 pa-1">
          <platform-icon :platform="rom.platform_slug"></platform-icon>
      </v-avatar>
    </v-chip>
    <v-chip-group v-if="rom.region || rom.revision" class="ml-3 pa-0 text-white text-shadow">
      <v-chip v-show="rom.region" size="x-small" class="bg-chip" label>
        {{ rom.region }}
      </v-chip>
      <v-chip v-show="rom.revision" size="x-small" class="bg-chip" label>
        {{ rom.revision }}
      </v-chip>
    </v-chip-group>
  </v-row>
</template>

<style scoped>
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
