<script setup lang="ts">
import type { PlatformSchema } from "@/__generated__";
import type { UserRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";
import { ref } from "vue";
import { useRouter } from "vue-router";

const props = defineProps<{ rom: UserRom; platform: PlatformSchema }>();
const router = useRouter();
const version = ref(props.rom.id);

function formatItem(rom: UserRom) {
  const langs = rom.languages.map((l) => languageToEmoji(l)).join(" ");
  const regions = rom.regions.map((r) => regionToEmoji(r)).join(" ");
  const tags = rom.tags.map((t) => `(${t})`).join(" ");
  if (langs || regions || tags) return `${langs} ${regions} ${tags}`;
  return rom.file_name;
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
    label="Version"
    variant="outlined"
    density="compact"
    class="version-select"
    hide-details
    v-model="version"
    @update:model-value="updateVersion"
    :items="
      [rom, ...rom.sibling_roms].map((i) => ({
        title: formatItem(i),
        value: i.id,
      }))
    "
  >
  </v-select>
</template>

<style scoped>
.version-select {
  max-width: fit-content;
}
</style>
