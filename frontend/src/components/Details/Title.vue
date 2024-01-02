<script setup lang="ts">
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import { regionToEmoji, languageToEmoji } from "@/utils";

const props = defineProps(["rom"]);
const { smAndUp } = useDisplay();
</script>
<template>
  <v-row no-gutters>
    <div
      class="text-h5 text-white text-shadow font-weight-bold title px-1"
      :class="{ 'text-truncate': smAndUp }"
    >
      {{ rom.name }}
    </div>
  </v-row>
  <v-row no-gutters class="align-center py-2">
    <v-chip
      class="font-italic text-white text-shadow title px-3"
      :to="`/platform/${rom.platform_slug}`"
    >
      {{ rom.platform_name || rom.platform_slug }}
      <v-avatar :rounded="0" size="40" class="ml-2 pa-1">
        <platform-icon :platform="rom.platform_slug"></platform-icon>
      </v-avatar>
    </v-chip>
    <v-chip
      class="text-white text-shadow title ml-2"
      v-if="rom.regions.filter((i) => i).length > 0"
      :title="`Regions: ${rom.regions.join(', ')}`"
    >
      <span class="px-1" v-for="region in rom.regions">{{
        regionToEmoji(region)
      }}</span>
    </v-chip>
    <v-chip
      class="text-white text-shadow title ml-2"
      v-if="rom.languages.filter((i) => i).length > 0"
      :title="`Languages: ${rom.languages.join(', ')}`"
    >
      <span class="px-1" v-for="language in rom.languages">{{
        languageToEmoji(language)
      }}</span>
    </v-chip>
    <v-chip v-show="rom.revision" class="text-white text-shadow title ml-2"
      >Revision {{ rom.revision }}
    </v-chip>
  </v-row>
</template>

<style scoped>
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
@/utils
