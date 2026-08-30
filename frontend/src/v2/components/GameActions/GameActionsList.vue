<script setup lang="ts">
// GameActionsList — the full RMenuItem list for a ROM, slotted into
// whatever RMenu mounts it. Single source of truth for the more-menu
// actions. Consumed by every MoreMenu dropdown (on GameCard, in the
// GameDetails header, …). Every action emits `close` after firing so the
// parent menu can dismiss.
//
// The metadata and destructive groups are permission-gated, so their
// leading dividers are conditional too — otherwise a read-only user gets
// a menu ending in stray separators.
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
    v-if="actions.canPlayInBrowser.value"
    :label="t('rom.play')"
    icon="mdi-play"
    @click="run(() => actions.play('local'))"
  />
  <RMenuItem
    v-if="actions.canPlayStream.value"
    :label="
      actions.streamLabel.value
        ? t('rom.stream-on', { container: actions.streamLabel.value })
        : t('rom.stream')
    "
    icon="mdi-play-network"
    @click="run(() => actions.play('stream'))"
  />
  <RMenuItem
    v-if="actions.canJoinStream.value"
    :label="
      actions.joinHostLabel.value
        ? t('rom.join-session-of', { user: actions.joinHostLabel.value })
        : t('rom.join-session')
    "
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
    v-if="actions.canDownload.value"
    :label="t('rom.copy-link')"
    icon="mdi-share-variant-outline"
    @click="run(actions.copyDownloadLink)"
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
