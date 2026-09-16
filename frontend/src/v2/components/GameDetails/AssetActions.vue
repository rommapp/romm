<script setup lang="ts">
// The per-item buttons of the Save data tab: visibility toggle and delete
// for the user's own saves and states, download for everything.
import { RBtn } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { Asset, AssetType } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    asset: Asset;
    type: AssetType;
    /** Own items also get the visibility toggle and delete. */
    own?: boolean;
    toggling?: boolean;
  }>(),
  { own: false, toggling: false },
);

const emit = defineEmits<{
  toggleVisibility: [];
  download: [];
  delete: [];
}>();

const { t } = useI18n();
</script>

<template>
  <!-- `display: contents`, so the buttons stay flex children of the slot. -->
  <span class="r-asset-actions" v-bind="$attrs">
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
