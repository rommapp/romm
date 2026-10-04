<script setup lang="ts" generic="T extends ScanType">
// ScanTypeSelect: the scan-type picker. Each row shows its description, or the
// reason it's disabled, under the title.
import { RSelect } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { ScanType, ScanTypeOption } from "@/v2/types/scan";

defineProps<{ items: ScanTypeOption<T>[] }>();
const scanType = defineModel<T>({ required: true });

const { t } = useI18n();
</script>

<template>
  <RSelect
    v-model="scanType"
    :items="items"
    :label="t('scan.scan-options')"
    prepend-inner-icon="mdi-magnify-scan"
    hide-details
    variant="outlined"
  >
    <template #item="{ props: itemProps, item }">
      <li v-bind="itemProps">
        <div class="r-select__item-stack">
          <div class="r-select__item-title">{{ item.title }}</div>
          <div
            v-if="item.raw.disabled || item.raw.subtitle"
            class="r-select__item-subtitle"
          >
            {{ item.raw.disabled || item.raw.subtitle }}
          </div>
        </div>
      </li>
    </template>
  </RSelect>
</template>
