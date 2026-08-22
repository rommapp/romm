<script setup lang="ts">
// MemoryCardImportDialog: the one-time prompt shown when a claim comes back
// 428 because the container still holds a memory card nobody has decided
// about. The claim is not held open behind this dialog, the answer is
// replayed on a fresh claim, so the only job here is to collect it.
//
// "discard" erases the card that is on the container, so it never gets the
// easy path: on "found" it sits beside the import action and asks for a
// confirmation, and on "unreadable" it is the only way forward and asks the
// user to type the keyword first, because nobody can say what is being lost.
import { RAlert, RBtn, RDialog } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { MemoryCardImportDetail } from "@/services/api/streaming";
import { formatBytes } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  detail: MemoryCardImportDetail | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "adopt"): void;
  (e: "discard"): void;
  (e: "cancel"): void;
}>();

const { t } = useI18n();
const confirm = useConfirm();

const unreadable = computed(() => props.detail?.outcome === "unreadable");
const summary = computed(() => props.detail?.summary ?? null);
const gameCodes = computed(() => summary.value?.game_codes ?? []);

function close(): void {
  emit("update:modelValue", false);
}

function onCancel(): void {
  close();
  emit("cancel");
}

function onAdopt(): void {
  close();
  emit("adopt");
}

// Both branches erase the container's card, so both confirm. The unreadable
// branch adds type-to-confirm: its contents are unknown, so the user cannot
// weigh what the erase costs.
async function onDiscard(): Promise<void> {
  const ok = await confirm({
    title: t("play.memory-card-import-discard-title"),
    body: t("play.memory-card-import-discard-body"),
    confirmText: t("play.memory-card-import-discard-confirm"),
    tone: "danger",
    ...(unreadable.value
      ? { requireTyped: t("play.memory-card-erase-keyword") }
      : {}),
  });
  if (!ok) return;
  close();
  emit("discard");
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-sd"
    :width="520"
    persistent
    @update:model-value="onCancel"
  >
    <template #header>
      <span>{{
        unreadable
          ? t("play.memory-card-unreadable-title")
          : t("play.memory-card-import-title")
      }}</span>
    </template>

    <template #content>
      <div v-if="unreadable" class="r-mc-import">
        <p class="r-mc-import__body">
          {{ t("play.memory-card-unreadable-body") }}
        </p>
        <RAlert
          v-if="detail?.reason"
          type="error"
          variant="translucent"
          density="compact"
          :text="
            t('play.memory-card-unreadable-reason', { reason: detail.reason })
          "
        />
        <p class="r-mc-import__warning">
          {{ t("play.memory-card-unreadable-warning") }}
        </p>
      </div>

      <div v-else class="r-mc-import">
        <p class="r-mc-import__body">
          {{
            t("play.memory-card-import-body", {
              count: summary?.file_count ?? 0,
            })
          }}
        </p>
        <p class="r-mc-import__meta">
          {{
            t("play.memory-card-import-size", {
              size: formatBytes(summary?.total_bytes ?? 0),
            })
          }}
        </p>
        <p v-if="gameCodes.length > 0" class="r-mc-import__meta">
          {{
            t("play.memory-card-import-games", { games: gameCodes.join(", ") })
          }}
        </p>
      </div>
    </template>

    <template #footer>
      <div class="r-mc-import__actions">
        <RBtn variant="text" @click="onCancel">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn variant="text" color="danger" @click="onDiscard">
          {{
            unreadable
              ? t("play.memory-card-unreadable-override")
              : t("play.memory-card-import-discard")
          }}
        </RBtn>
        <RBtn
          v-if="!unreadable"
          variant="flat"
          color="primary"
          prepend-icon="mdi-download"
          @click="onAdopt"
        >
          {{ t("play.memory-card-import-adopt") }}
        </RBtn>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-mc-import {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-mc-import__body {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-mc-import__meta {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-mc-import__warning {
  margin: 0;
  color: var(--r-color-danger-fg);
  font-size: var(--r-font-size-sm);
}

.r-mc-import__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--r-space-2);
  width: 100%;
}
</style>
