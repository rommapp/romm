<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { identity } from "lodash";
import { computed } from "vue";
import { type SimpleRom } from "@/stores/roms";
import {
  languageToEmoji,
  regionToEmoji,
  getEmojiForStatus,
  getTextForStatus,
} from "@/utils";

const props = defineProps<{ rom: SimpleRom }>();
const showRegions = useLocalStorage("settings.showRegions", true);
const showLanguages = useLocalStorage("settings.showLanguages", true);
const showStatus = useLocalStorage("settings.showStatus", true);

const playingStatus = computed(() => {
  const { now_playing, backlogged, status } = props.rom?.rom_user ?? {};
  if (now_playing) return "now_playing";
  if (backlogged) return "backlogged";
  return status || "";
});
</script>

<template>
  <v-chip
    v-if="rom.regions.filter(identity).length > 0 && showRegions"
    :title="`Regions: ${rom.regions.join(', ')}`"
    class="translucent mr-1 mt-1 px-1"
    :class="{ 'emoji-collection': rom.regions.length > 3 }"
    density="compact"
  >
    <span v-for="region in rom.regions.slice(0, 3)" :key="region" class="emoji">
      {{ regionToEmoji(region) }}
    </span>
  </v-chip>
  <v-chip
    v-if="rom.languages.filter(identity).length > 0 && showLanguages"
    :title="`Languages: ${rom.languages.join(', ')}`"
    class="translucent mr-1 mt-1 px-1"
    :class="{ 'emoji-collection': rom.languages.length > 3 }"
    density="compact"
  >
    <span
      v-for="language in rom.languages.slice(0, 3)"
      :key="language"
      class="emoji"
    >
      {{ languageToEmoji(language) }}
    </span>
  </v-chip>
  <v-chip
    v-if="playingStatus && showStatus"
    class="translucent mr-1 mt-1 px-2"
    density="compact"
    :title="getTextForStatus(playingStatus)"
  >
    {{ getEmojiForStatus(playingStatus) }}
  </v-chip>
</template>
