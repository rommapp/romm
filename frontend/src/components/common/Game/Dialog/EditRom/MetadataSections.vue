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
    metadataType: "igdb",
    metadataField: "igdb_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/igdb.png",
    label: "IGDB",
  },
  {
    metadataType: "moby",
    metadataField: "moby_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/moby.png",
    label: "MobyGames",
  },
  {
    metadataType: "ss",
    metadataField: "ss_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/ss.png",
    label: "ScreenScraper",
  },
  {
    metadataType: "launchbox",
    metadataField: "launchbox_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/launchbox.png",
    label: "LaunchBox",
  },
  {
    metadataType: "hasheous",
    metadataField: "hasheous_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/hasheous.png",
    label: "Hasheous",
  },
  {
    metadataType: "flashpoint",
    metadataField: "flashpoint_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/flashpoint.png",
    label: "Flashpoint",
  },
  {
    metadataType: "hltb",
    metadataField: "hltb_metadata" as keyof SimpleRom,
    iconSrc: "/assets/scrappers/hltb.png",
    label: "HLTB",
  },
];
</script>

<template>
  <template v-for="config in metadataConfigs" :key="config.metadataType">
    <RawMetadataPanel
      :rom="rom"
      :metadata-type="config.metadataType"
      :metadata-field="config.metadataField"
      :icon-src="config.iconSrc"
      :label="config.label"
      @update:rom="handleRomUpdate"
    />
  </template>
</template>
