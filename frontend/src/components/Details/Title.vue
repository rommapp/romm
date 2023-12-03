<script setup>
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import { regionToEmoji, languageToEmoji } from "@/utils/utils";

const props = defineProps(["rom"]);
const { smAndUp } = useDisplay();
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
    <v-chip-group class="ml-3 pa-0 text-white text-shadow">
      <v-chip v-if="rom.regions.length > 0" title="Regions">
        <span v-for="region in rom.regions">{{ regionToEmoji(region) }}&nbsp;</span>
      </v-chip>
      <v-chip v-if="rom.languages.length > 0" title="Languages">
        <span v-for="language in rom.languages">{{ languageToEmoji(language) }}&nbsp;</span>
      </v-chip>
      <v-chip v-show="rom.revision">
        Rev {{ rom.revision }}
      </v-chip>
    </v-chip-group>
  </v-row>
</template>

<style scoped>
.text-shadow {
  text-shadow: 1px 1px 3px #000000, 0 0 3px #000000;
}
</style>
