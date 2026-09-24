<script setup lang="ts">
// The per-item buttons of the Save data tab: download for everything, then
// edit, favorite and delete for own saves and states.
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { Asset, AssetType } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    asset: Asset;
    type: AssetType;
    /** Own items also get edit, the heart and delete. */
    own?: boolean;
    favoriting?: boolean;
  }>(),
  { own: false, favoriting: false },
);

const emit = defineEmits<{
  download: [];
  edit: [];
  toggleFavorite: [];
  delete: [];
}>();

const { t } = useI18n();

const favoriteLabel = computed(() =>
  props.asset.is_favorite
    ? t("rom.remove-from-favorites")
    : t("rom.add-to-favorites"),
);
const editLabel = computed(() =>
  props.type === "save" ? t("rom.edit-save") : t("rom.edit-state"),
);
</script>

<template>
  <!-- `display: contents`, so the buttons stay flex children of the slot. -->
  <span class="r-asset-actions" v-bind="$attrs">
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
      icon="mdi-pencil-outline"
      variant="text"
      size="small"
      :tooltip="editLabel"
      :aria-label="editLabel"
      @click="emit('edit')"
    />
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
