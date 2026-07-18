<script setup lang="ts">
// GameActionsList — the full RMenuItem list for a ROM, slotted into
// whatever RMenu mounts it. Single source of truth for the more-menu
// actions. Consumed by every MoreMenu dropdown (on GameCard, in the
// GameDetails header, …). Every action emits `close` after firing so the
// parent menu can dismiss.
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

function run(fn: () => void | Promise<void>) {
  void fn();
  emit("close");
}
</script>

<template>
  <!-- Primary actions -->
  <RMenuItem
    v-if="actions.canPlay.value"
    :label="t('rom.play')"
    icon="mdi-play"
    @click="run(actions.play)"
  />
  <RMenuItem
    :label="t('rom.download')"
    icon="mdi-download-outline"
    @click="run(actions.download)"
  />
  <RMenuItem
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

  <RDivider />

  <!-- Metadata actions -->
  <RMenuItem
    :label="t('rom.match-rom')"
    icon="mdi-magnify"
    @click="run(actions.match)"
  />
  <RMenuItem
    :label="t('rom.refresh-metadata')"
    icon="mdi-refresh"
    @click="run(actions.refreshMetadata)"
  />
  <RMenuItem
    :label="t('common.edit')"
    icon="mdi-pencil-outline"
    @click="run(actions.edit)"
  />

  <RDivider />

  <!-- Destructive -->
  <RMenuItem
    :label="t('common.delete')"
    icon="mdi-trash-can-outline"
    variant="danger"
    @click="run(actions.remove)"
  />
</template>
