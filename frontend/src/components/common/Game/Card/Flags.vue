<script setup lang="ts">
import { computed } from "vue";
import { type SimpleRom } from "@/stores/roms.js";
import {
  languageToEmoji,
  regionToEmoji,
  getEmojiForStatus,
  getTextForStatus,
} from "@/utils";
import { identity, isNull } from "lodash";

const props = defineProps<{ rom: SimpleRom }>();
const showRegions = isNull(localStorage.getItem("settings.showRegions"))
  ? true
  : localStorage.getItem("settings.showRegions") === "true";
const showLanguages = isNull(localStorage.getItem("settings.showLanguages"))
  ? true
  : localStorage.getItem("settings.showLanguages") === "true";
const showSiblings = isNull(localStorage.getItem("settings.showSiblings"))
  ? true
  : localStorage.getItem("settings.showSiblings") === "true";
const showStatus = isNull(localStorage.getItem("settings.showStatus"))
  ? true
  : localStorage.getItem("settings.showStatus") === "true";

const playingStatus = computed(() => {
  if (props.rom.rom_user.now_playing) return "now_playing";
  if (props.rom.rom_user.backlogged) return "backlogged";
  return props.rom.rom_user.status;
});
</script>

<template>
  <v-chip
    v-if="rom.regions.filter(identity).length > 0 && showRegions"
    :title="`Regions: ${rom.regions.join(', ')}`"
    class="translucent-dark mr-1 mt-1 px-1"
    :class="{ 'emoji-collection': rom.regions.length > 3 }"
    density="compact"
  >
    <span class="emoji" v-for="region in rom.regions.slice(0, 3)">
      {{ regionToEmoji(region) }}
    </span>
  </v-chip>
  <v-chip
    v-if="rom.languages.filter(identity).length > 0 && showLanguages"
    :title="`Languages: ${rom.languages.join(', ')}`"
    class="translucent-dark mr-1 mt-1 px-1"
    :class="{ 'emoji-collection': rom.languages.length > 3 }"
    density="compact"
  >
    <span class="emoji" v-for="language in rom.languages.slice(0, 3)">
      {{ languageToEmoji(language) }}
    </span>
  </v-chip>
  <v-chip
    v-if="playingStatus && showStatus"
    class="translucent-dark mr-1 mt-1"
    density="compact"
    :title="getTextForStatus(playingStatus)"
  >
    {{ getEmojiForStatus(playingStatus) }}
  </v-chip>
  <v-chip
    v-if="rom.sibling_roms && rom.sibling_roms.length > 0 && showSiblings"
    class="translucent-dark mr-1 mt-1"
    density="compact"
  >
    +{{ rom.sibling_roms.length }}
  </v-chip>
</template>
