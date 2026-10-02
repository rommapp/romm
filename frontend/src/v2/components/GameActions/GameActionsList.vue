<script setup lang="ts">
import { RDivider, RMenuItem } from "@v2/lib";
import { computed, toRef } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: SimpleRom | null }>();

const emit = defineEmits<{ (e: "close"): void }>();

const { t } = useI18n();
const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);

const favLabel = computed(() =>
  actions.isFavorited.value
    ? t("rom.remove-from-favorites")
    : t("rom.add-to-favorites"),
);

const hasMetadataActions = computed(
  () =>
    actions.canMatch.value || actions.canRefresh.value || actions.canEdit.value,
);

function run(fn: () => void | Promise<void>) {
  void fn();
  emit("close");
}
</script>

<template>
  <!-- Primary actions -->
  <RMenuItem
    v-if="actions.canPlayLocally.value"
    :label="t('rom.play')"
    icon="mdi-play"
    @click="run(() => actions.play('local'))"
  />
  <RMenuItem
    v-if="actions.canPlayStream.value"
    :label="actions.streamActionLabel.value"
    icon="mdi-play-network"
    @click="run(() => actions.play('stream'))"
  />
  <RMenuItem
    v-if="actions.canJoinStream.value"
    :label="actions.joinActionLabel.value"
    icon="mdi-account-multiple-plus"
    @click="run(actions.joinStream)"
  />
  <RMenuItem
    v-if="actions.canDownload.value"
    :label="t('rom.download')"
    icon="mdi-download-outline"
    @click="run(actions.download)"
  />
  <RMenuItem
    v-for="format in actions.downloadFormats.value"
    :key="format"
    :label="t('rom.download-as', { format: format.toUpperCase() })"
    icon="mdi-file-download-outline"
    @click="run(() => actions.downloadAs(format))"
  />
  <RMenuItem
    v-if="actions.canDownload.value"
    :label="t('rom.copy-link')"
    icon="mdi-share-variant-outline"
    @click="run(actions.copyDownloadLink)"
  />
  <RMenuItem
    v-if="actions.canInstallOnDevice.value"
    :label="t('rom.install-on-device')"
    icon="mdi-cellphone-arrow-down"
    @click="run(actions.installOnDevice)"
  />
  <RMenuItem
    v-if="actions.canShareQR.value"
    :label="t('rom.share-qr')"
    icon="mdi-qrcode"
    @click="run(actions.shareQR)"
  />
  <RMenuItem
    v-if="actions.canOpenInFlashpoint.value"
    :label="t('rom.open-in-flashpoint')"
    icon="mdi-rocket-launch-outline"
    @click="run(actions.openInFlashpoint)"
  />

  <RDivider />

  <!-- User actions -->
  <RMenuItem
    :label="favLabel"
    :icon="actions.isFavorited.value ? 'mdi-heart' : 'mdi-heart-outline'"
    :variant="actions.isFavorited.value ? 'active' : 'default'"
    @click="run(actions.favorite)"
  />
  <RMenuItem
    v-if="actions.canManageCollections.value"
    :label="t('rom.manage-collections')"
    icon="mdi-bookmark-outline"
    @click="run(actions.manageCollections)"
  />
  <RMenuItem
    v-if="actions.canRemoveFromContinuePlaying.value"
    :label="t('rom.remove-from-playing')"
    icon="mdi-play-protected-content"
    @click="run(actions.removeFromContinuePlaying)"
  />

  <RDivider v-if="hasMetadataActions" />

  <!-- Metadata actions -->
  <RMenuItem
    v-if="actions.canMatch.value"
    :label="t('rom.match-rom')"
    icon="mdi-magnify"
    @click="run(actions.match)"
  />
  <RMenuItem
    v-if="actions.canRefresh.value"
    :label="t('rom.refresh-metadata')"
    icon="mdi-refresh"
    @click="run(actions.refreshMetadata)"
  />
  <RMenuItem
    v-if="actions.canRefresh.value"
    :label="t('rom.refresh-files')"
    icon="mdi-file-refresh-outline"
    @click="run(actions.refreshFiles)"
  />
  <RMenuItem
    v-if="actions.canEdit.value"
    :label="t('common.edit')"
    icon="mdi-pencil-outline"
    @click="run(actions.edit)"
  />

  <RDivider v-if="actions.canDelete.value" />

  <!-- Destructive -->
  <RMenuItem
    v-if="actions.canDelete.value"
    :label="t('common.delete')"
    icon="mdi-trash-can-outline"
    variant="danger"
    @click="run(actions.remove)"
  />
</template>
