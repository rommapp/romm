<script setup lang="ts">
// GameActionsList — the full RMenuItem list for a ROM, slotted into
// whatever RMenu mounts it. Single source of truth for the more-menu
// actions. Consumed by every MoreMenu dropdown (on GameCard, in the
// GameDetails header, …). Every action emits `close` after firing so the
// parent menu can dismiss.
import { RDivider, RMenuItem } from "@v2/lib";
import { computed, toRef } from "vue";
import type { SimpleRom } from "@/stores/roms";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: SimpleRom | null }>();

const emit = defineEmits<{ (e: "close"): void }>();

const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);

const favLabel = computed(() =>
  actions.isFavorited.value ? "Remove from favorites" : "Add to favorites",
);

function run(fn: () => void | Promise<void>) {
  void fn();
  emit("close");
}
</script>

<template>
  <!-- Primary actions -->
  <RMenuItem label="Play" icon="mdi-play" @click="run(actions.play)" />
  <RMenuItem
    label="Download"
    icon="mdi-download-outline"
    @click="run(actions.download)"
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
    label="Manage collections"
    icon="mdi-bookmark-outline"
    @click="run(actions.manageCollections)"
  />
  <RMenuItem
    v-if="actions.canShareQR.value"
    label="Share (QR code)"
    icon="mdi-qrcode"
    @click="run(actions.shareQR)"
  />

  <RDivider />

  <!-- Metadata actions -->
  <RMenuItem label="Match ROM" icon="mdi-magnify" @click="run(actions.match)" />
  <RMenuItem
    label="Refresh metadata"
    icon="mdi-refresh"
    @click="run(actions.refreshMetadata)"
  />
  <RMenuItem
    label="Edit"
    icon="mdi-pencil-outline"
    @click="run(actions.edit)"
  />

  <RDivider />

  <!-- Destructive -->
  <RMenuItem
    label="Delete"
    icon="mdi-trash-can-outline"
    variant="danger"
    @click="run(actions.remove)"
  />
</template>
