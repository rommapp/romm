<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { regionToEmoji, languageToEmoji } from "@/utils/utils";

const props = defineProps(["rom"]);
const router = useRouter();
const version = ref(props.rom.id);

function formatItem(rom) {
  const langs = rom.languages.map((l) => languageToEmoji(l)).join(" ");
  const regions = rom.regions.map((r) => regionToEmoji(r)).join(" ");
  const tags = rom.tags.map((t) => `(${t})`).join(" ");
  return `${langs} ${regions} ${tags}`;
}

function updateVersion() {
  router.push({
    path: `/platform/${props.rom.platform_slug}/${version.value}`,
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
  /* position: absolute; */
  max-width: fit-content;
  /* min-width: 8rem; */
}
</style>
