<script setup lang="ts">
// The per-item buttons of the Save data tab: favorite, labels, visibility
// toggle and delete for own saves and states, download for everything.
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Asset, AssetType } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    asset: Asset;
    type: AssetType;
    /** Own items also get the heart, labels, visibility toggle and delete. */
    own?: boolean;
    toggling?: boolean;
    favoriting?: boolean;
  }>(),
  { own: false, toggling: false, favoriting: false },
);

const emit = defineEmits<{
  toggleFavorite: [];
  editLabels: [];
  toggleVisibility: [];
  download: [];
  delete: [];
}>();

const { t } = useI18n();

const hasLabels = computed(() => (props.asset.labels ?? []).length > 0);
const favoriteLabel = computed(() =>
  props.asset.is_favorite
    ? t("rom.remove-from-favorites")
    : t("rom.add-to-favorites"),
);
const labelsLabel = computed(() =>
  hasLabels.value ? t("rom.edit-labels") : t("rom.add-labels"),
);
</script>

<template>
  <!-- `display: contents`, so the buttons stay flex children of the slot. -->
  <span class="r-asset-actions" v-bind="$attrs">
    <RBtn
      v-if="own"
      :icon="asset.is_favorite ? 'mdi-heart' : 'mdi-heart-outline'"
      variant="text"
      size="small"
      :color="asset.is_favorite ? 'primary' : undefined"
      :loading="favoriting"
      :tooltip="favoriteLabel"
      :aria-label="favoriteLabel"
      :aria-pressed="!!asset.is_favorite"
      @click="emit('toggleFavorite')"
    />
    <RBtn
      v-if="own"
      icon="mdi-label-outline"
      variant="text"
      size="small"
      :color="hasLabels ? 'primary' : undefined"
      :tooltip="labelsLabel"
      :aria-label="labelsLabel"
      @click="emit('editLabels')"
    />
    <RBtn
      v-if="own"
      :icon="asset.is_public ? 'mdi-lock-open-variant' : 'mdi-lock'"
      variant="text"
      size="small"
      :color="asset.is_public ? 'var(--r-color-fg-muted)' : 'primary'"
      :loading="toggling"
      :tooltip="asset.is_public ? t('rom.make-private') : t('rom.make-public')"
      :aria-label="
        asset.is_public ? t('rom.make-private') : t('rom.make-public')
      "
      @click="emit('toggleVisibility')"
    />
    <RBtn
      icon="mdi-download-outline"
      variant="text"
      size="small"
      :tooltip="t('common.download')"
      :aria-label="t('rom.download-named', { name: asset.file_name })"
      @click="emit('download')"
    />
    <RBtn
      v-if="own"
      icon="mdi-delete-outline"
      variant="text"
      size="small"
      color="romm-red"
      :tooltip="t('common.delete')"
      :aria-label="
        type === 'save' ? t('rom.delete-save') : t('rom.delete-state')
      "
      @click="emit('delete')"
    />
  </span>
</template>

<style scoped>
.r-asset-actions {
  display: contents;
}
</style>
