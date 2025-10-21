<script setup lang="ts">
import type { UpdateRom } from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import RawMetadataPanel from "./RawMetadataPanel.vue";

defineProps<{ rom: SimpleRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

const handleRomUpdate = (updatedRom: UpdateRom) => {
  emit("update:rom", updatedRom);
};

const metadataConfigs = [
  {
    metadataField: "igdb_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/igdb.png",
    label: "IGDB",
  },
  {
    metadataField: "moby_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/moby.png",
    label: "MobyGames",
  },
  {
    metadataField: "ss_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/ss.png",
    label: "ScreenScraper",
  },
  {
    metadataField: "launchbox_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/launchbox.png",
    label: "LaunchBox",
  },
  {
    metadataField: "hasheous_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/hasheous.png",
    label: "Hasheous",
  },
  {
    metadataField: "flashpoint_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/flashpoint.png",
    label: "Flashpoint",
  },
  {
    metadataField: "hltb_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/hltb.png",
    label: "HLTB",
  },
];
</script>

<template>
  <template v-for="config in metadataConfigs" :key="config.metadataField">
    <RawMetadataPanel
      :rom="rom"
      :metadata-field="config.metadataField"
      :icon-src="config.iconSrc"
      :label="config.label"
      @update:rom="handleRomUpdate"
    />
  </template>
</template>
