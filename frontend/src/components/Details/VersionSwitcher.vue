<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import type { DetailedRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { ref } from "vue";
import { useRouter } from "vue-router";

// Props
const props = defineProps<{ rom: DetailedRom; platform: Platform }>();
const router = useRouter();
const version = ref(props.rom.id);

// Functions
function formatTitle(rom: DetailedRom) {
  const langs = rom.languages.map((l) => languageToEmoji(l)).join(" ");
  const regions = rom.regions.map((r) => regionToEmoji(r)).join(" ");
  const tags = rom.tags.map((t) => `(${t})`).join(" ");
  return `${langs} ${regions} ${tags}`.trim();
}

function updateVersion() {
  router.push({
    name: "rom",
    params: { rom: version.value },
  });
}
</script>

<template>
  <v-select
    v-model="version"
    label="Version"
    single-line
    rounded="0"
    variant="solo-filled"
    density="compact"
    max-width="fit-content"
    hide-details
    :items="
      [rom, ...rom.sibling_roms].map((i) => ({
        title: formatTitle(i),
        value: i.id,
      }))
    "
    @update:model-value="updateVersion"
  />
</template>
