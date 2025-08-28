<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import { ref } from "vue";
import { useRouter } from "vue-router";

const props = defineProps<{ rom: DetailedRom }>();
const router = useRouter();
const version = ref(props.rom.id);

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
      [rom, ...rom.siblings].map((i) => ({
        title: i.fs_name_no_ext,
        value: i.id,
      }))
    "
    @update:model-value="updateVersion"
  />
</template>
