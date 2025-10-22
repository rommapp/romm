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

const metadataConfigs: {
  idField: keyof SimpleRom;
  metadataField: keyof SimpleRom;
  iconSrc: string;
  label: string;
}[] = [
  {
    idField: "igdb_id",
    metadataField: "igdb_metadata",
    iconSrc: "/assets/scrappers/igdb.png",
    label: "IGDB",
  },
  {
    idField: "moby_id",
    metadataField: "moby_metadata",
    iconSrc: "/assets/scrappers/moby.png",
    label: "MobyGames",
  },
  {
    idField: "ss_id",
    metadataField: "ss_metadata",
    iconSrc: "/assets/scrappers/ss.png",
    label: "ScreenScraper",
  },
  {
    idField: "launchbox_id",
    metadataField: "launchbox_metadata",
    iconSrc: "/assets/scrappers/launchbox.png",
    label: "LaunchBox",
  },
  {
    idField: "hasheous_id",
    metadataField: "hasheous_metadata",
    iconSrc: "/assets/scrappers/hasheous.png",
    label: "Hasheous",
  },
  {
    idField: "flashpoint_id",
    metadataField: "flashpoint_metadata",
    iconSrc: "/assets/scrappers/flashpoint.png",
    label: "Flashpoint",
  },
  {
    idField: "hltb_id",
    metadataField: "hltb_metadata",
    iconSrc: "/assets/scrappers/hltb.png",
    label: "HLTB",
  },
];
</script>

<template>
  <template v-for="config in metadataConfigs" :key="config.idField">
    <RawMetadataPanel
      v-if="rom[config.idField]"
      :rom="rom"
      :metadata-field="config.metadataField"
      :icon-src="config.iconSrc"
      :label="config.label"
      @update:rom="handleRomUpdate"
    />
  </template>
</template>
