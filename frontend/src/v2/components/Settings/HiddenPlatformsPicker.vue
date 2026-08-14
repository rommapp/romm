<script setup lang="ts">
// HiddenPlatformsPicker — pick platforms to hide from a user or group. Model
// is the list of hidden platform ids. The dropdown is the shared
// PlatformSelect (the same icon + name rows used by Scan), in multi-select
// mode so several platforms can be toggled without the menu closing each
// time; the activator shows a count and the picked platforms render below as
// a removable list (icon + name), not pills.
import { RBtn, RPlatformIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ modelValue: number[]; platforms: Platform[] }>();
const emit = defineEmits<{ "update:modelValue": [number[]] }>();

const { t } = useI18n();

const byId = computed(() => {
  const m = new Map<number, Platform>();
  for (const p of props.platforms) m.set(p.id, p);
  return m;
});

const selected = computed(() =>
  props.modelValue
    .map((id) => byId.value.get(id))
    .filter((p): p is Platform => p !== undefined),
);

function onUpdate(value: number | string | number[] | string[] | null) {
  if (!Array.isArray(value)) return;
  emit(
    "update:modelValue",
    value.filter((v): v is number => typeof v === "number"),
  );
}

function remove(id: number) {
  emit(
    "update:modelValue",
    props.modelValue.filter((x) => x !== id),
  );
}
</script>

<template>
  <div class="r-v2-hidplat">
    <PlatformSelect
      :model-value="modelValue"
      :items="platforms"
      item-key="id"
      multiple
      :chips="false"
      prepend-inner-icon="mdi-controller"
      searchable
      show-meta
      hide-details
      :placeholder="t('settings.hidden-platforms-placeholder')"
      @update:model-value="onUpdate"
    >
      <!-- One count summary for the whole selection; an empty node for the
           rest suppresses RSelect's per-item default (which would otherwise
           reprint every platform's icon + name next to the count). -->
      <template #selection="{ index }">
        <span v-if="index === 0" class="r-v2-hidplat__count">
          {{ t("common.platforms-n", modelValue.length) }}
        </span>
        <span v-else aria-hidden="true" />
      </template>
    </PlatformSelect>

    <ul v-if="selected.length" class="r-v2-hidplat__list">
      <li v-for="p in selected" :key="p.id" class="r-v2-hidplat__row">
        <RPlatformIcon
          :slug="p.slug"
          :fs-slug="p.fs_slug"
          :name="p.display_name"
          :size="24"
          :show-tooltip="false"
        />
        <span class="r-v2-hidplat__name">{{ p.display_name }}</span>
        <RBtn
          variant="text"
          icon="mdi-close"
          size="small"
          class="r-v2-hidplat__remove"
          :aria-label="t('common.remove')"
          @click="remove(p.id)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.r-v2-hidplat {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-hidplat__count {
  color: var(--r-color-fg-secondary);
}
.r-v2-hidplat__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-hidplat__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--r-color-surface);
}
.r-v2-hidplat__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-hidplat__remove {
  flex: none;
}
</style>
