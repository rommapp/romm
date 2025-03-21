<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import type { RomSchema } from "@/__generated__";
import { ref } from "vue";
import { useRouter } from "vue-router";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const router = useRouter();
const version = ref(props.rom.id);

// Functions
function formatTitle(rom: RomSchema) {
  const langs = rom.languages.map((l) => languageToEmoji(l)).join(" ");
  const regions = rom.regions.map((r) => regionToEmoji(r)).join(" ");
  const revision = rom.revision ? `[rev-${rom.revision}]` : "";
  const tags = rom.tags.map((t) => `(${t})`).join(" ");
  return `${langs} ${regions} ${revision} ${tags}`.trim();
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
