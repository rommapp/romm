<script setup lang="ts">
// MetadataSections (v2) — fans out one RCollapsible per metadata
// provider whose ID is set on the rom. The collapsible body is the
// per-provider raw-JSON editor (RawMetadataPanel). Providers without
// an ID for this rom are skipped so the dialog only ever shows panels
// that actually have data.
//
// Feature composite — knows the SimpleRom shape and the v2 R
// primitives. EditRomDialog renders this alongside AdditionalDetails
// and MetadataIdSection inside the metadata accordion.
import { RAvatar, RCollapsible } from "@v2/lib";
import { ref } from "vue";
import type { UpdateRom } from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import RawMetadataPanel from "./RawMetadataPanel.vue";

defineProps<{ rom: SimpleRom }>();

const emit = defineEmits<{
  "update:rom": [rom: UpdateRom];
}>();

function handleRomUpdate(updatedRom: UpdateRom) {
  emit("update:rom", updatedRom);
}

interface MetadataConfig {
  idField: keyof SimpleRom;
  metadataField: keyof SimpleRom;
  iconSrc: string;
  label: string;
}

const METADATA_CONFIGS: readonly MetadataConfig[] = [
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

// Each panel keeps its own open state. Keyed by metadataField so the
// state survives across rom mutations (the parent re-renders us when
// the user saves any provider's raw payload).
const openMap = ref<Record<string, boolean>>({});
function isOpen(key: string) {
  return openMap.value[key] === true;
}
function setOpen(key: string, value: boolean) {
  openMap.value = { ...openMap.value, [key]: value };
}
</script>

<template>
  <template v-for="config in METADATA_CONFIGS" :key="config.idField">
    <RCollapsible
      v-if="rom[config.idField]"
      :model-value="isOpen(String(config.metadataField))"
      class="r-v2-meta-section"
      @update:model-value="(v) => setOpen(String(config.metadataField), v)"
    >
      <template #header-prepend>
        <RAvatar :image="config.iconSrc" size="24" rounded="sm" />
      </template>
      <template #title> {{ config.label }} metadata </template>
      <RawMetadataPanel
        :rom="rom as unknown as UpdateRom"
        :metadata-field="config.metadataField as keyof UpdateRom"
        :label="config.label"
        @update:rom="handleRomUpdate"
      />
    </RCollapsible>
  </template>
</template>

<style scoped>
.r-v2-meta-section {
  margin-bottom: 8px;
}
.r-v2-meta-section:last-child {
  margin-bottom: 0;
}
</style>
