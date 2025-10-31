<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import type { RomFileSchema } from "@/__generated__";
import { formatBytes } from "@/utils";

const { t } = useI18n();

const props = defineProps<{
  item: RomFileSchema;
}>();

const fileInfo = ref([
  { label: "Size", value: formatBytes(props.item.file_size_bytes) },
  {
    label: "SHA-1",
    value: props.item.sha1_hash
      ? props.item.sha1_hash.substring(0, 6) +
        "..." +
        props.item.sha1_hash.substring(props.item.sha1_hash.length - 6)
      : null,
  },
  {
    label: "MD5",
    value: props.item.md5_hash
      ? props.item.md5_hash.substring(0, 6) +
        "..." +
        props.item.md5_hash.substring(props.item.md5_hash.length - 6)
      : null,
  },
  { label: "CRC", value: props.item.crc_hash },
]);
</script>
<template>
  <v-chip v-if="item.category" color="primary" size="x-small" class="mr-1">
    {{ item.category.toLocaleUpperCase() }}
  </v-chip>
  <template v-for="info in fileInfo" :key="info.label">
    <v-chip v-if="info.value" size="x-small" class="px-0 mr-1" label>
      <v-chip label size="x-small">
        {{ info.label }}
      </v-chip>
      <span class="px-2">{{ info.value }}</span>
    </v-chip>
  </template>
</template>
