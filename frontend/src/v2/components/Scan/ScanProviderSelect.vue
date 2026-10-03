<script setup lang="ts">
// ScanProviderSelect: one labelled group of the scan provider picker. Binding
// `launchbox-remote` adds LaunchBox's Local/Cloud toggle to its dropdown row.
import { RAvatar, RSelect, RSwitch, RTooltip } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { MetadataOption } from "@/stores/heartbeat";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    items: MetadataOption[];
    label: string;
    icon: string;
    launchboxSelected?: boolean;
    launchboxRemote?: boolean;
  }>(),
  // An explicit undefined stops Vue casting an unbound boolean prop to false.
  { launchboxSelected: false, launchboxRemote: undefined },
);
const sources = defineModel<MetadataOption[]>({ required: true });
const emit = defineEmits<{
  "update:allSelected": [value: boolean];
  "update:launchboxRemote": [value: boolean];
}>();

const { t } = useI18n();
</script>

<template>
  <div class="r-v2-provider-select" v-bind="$attrs">
    <span class="r-v2-provider-select__label">{{ label }}</span>
    <RSelect
      v-model="sources"
      :items="items"
      :label="label"
      item-title="name"
      :prepend-inner-icon="icon"
      variant="outlined"
      multiple
      return-object
      clearable
      hide-details
      chips
      chip-tone="plain"
      show-all-option
      @update:all-selected="emit('update:allSelected', $event)"
    >
      <template #chip="{ item }">
        <RTooltip :text="item.raw.name" location="bottom">
          <template #activator="{ props: tipProps }">
            <span
              v-bind="tipProps"
              class="r-v2-provider-select__chip"
              :aria-label="item.raw.name"
            >
              <RAvatar :image="item.raw.logo_path" size="18" rounded="sm" />
            </span>
          </template>
        </RTooltip>
      </template>
      <template #item="{ props: itemProps, item }">
        <li v-bind="itemProps">
          <RAvatar :image="item.raw.logo_path" size="22" rounded="sm" />
          <div class="r-select__item-stack">
            <div class="r-select__item-title">
              {{ item.raw.name }}
            </div>
            <div v-if="item.raw.disabled" class="r-select__item-subtitle">
              {{ item.raw.disabled }}
            </div>
          </div>

          <div
            v-if="
              item.raw.value === 'launchbox' && launchboxRemote !== undefined
            "
            class="r-v2-provider-select__lb-toggle"
            @click.stop
            @mousedown.stop
          >
            <span
              class="r-v2-provider-select__lb-label"
              :class="{
                'r-v2-provider-select__lb-inactive': launchboxRemote,
              }"
            >
              {{ t("rom.launchbox-local") }}
            </span>
            <RSwitch
              :model-value="launchboxRemote"
              :disabled="!launchboxSelected"
              :aria-label="t('rom.launchbox-cloud-source')"
              @update:model-value="emit('update:launchboxRemote', $event)"
            />
            <span
              class="r-v2-provider-select__lb-label"
              :class="{
                'r-v2-provider-select__lb-inactive': !launchboxRemote,
              }"
            >
              {{ t("rom.launchbox-cloud") }}
            </span>
          </div>
        </li>
      </template>
    </RSelect>
  </div>
</template>

<style scoped>
.r-v2-provider-select {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-provider-select + .r-v2-provider-select {
  margin-top: 8px;
}

.r-v2-provider-select__label {
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0.04em;
  color: var(--r-color-fg-faint);
}

.r-v2-provider-select__chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.r-v2-provider-select__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.r-v2-provider-select__lb-label {
  font-size: 11px;
  color: var(--r-color-fg);
  white-space: nowrap;
}

.r-v2-provider-select__lb-inactive {
  color: var(--r-color-fg-muted);
}
</style>
