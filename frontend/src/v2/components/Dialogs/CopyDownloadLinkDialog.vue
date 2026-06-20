<script setup lang="ts">
// CopyDownloadLinkDialog — fallback surface for `useGameActions.copyDownloadLink`
// when the Clipboard API isn't usable (insecure context, denied
// permission, older browsers). Renders the link in a selectable box so
// the user can copy it by hand, and offers a Retry button that tries
// the Clipboard API once more in case the original failure was a
// permission prompt the user has now accepted.
import { RBtn, RDialog } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const show = ref(false);
const link = ref("");
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const openHandler = (downloadLink: string) => {
  link.value = downloadLink;
  show.value = true;
};
emitter?.on("showCopyDownloadLinkDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showCopyDownloadLinkDialog", openHandler));

function closeDialog() {
  show.value = false;
  link.value = "";
}

async function retryCopy() {
  if (!link.value) return;
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(link.value);
      snackbar.success(t("rom.snackbar-download-link-copied"), {
        icon: "mdi-link-variant",
      });
      closeDialog();
      return;
    } catch {
      // stays open so the user can still select the text manually
    }
  }
  snackbar.error(t("rom.cant-copy-link"), {
    icon: "mdi-alert-circle-outline",
  });
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-share-variant-outline"
    width="560"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.copy-link") }}</span>
    </template>
    <template #content>
      <div class="r-v2-copy-link">
        <p class="r-v2-copy-link__hint">
          {{ t("common.clipboard-unavailable") }}
        </p>
        <code class="r-v2-copy-link__box">{{ link }}</code>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="closeDialog">{{ t("common.close") }}</RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-content-copy"
        @click="retryCopy"
      >
        {{ t("common.try-again") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-copy-link {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 4px 0;
}

.r-v2-copy-link__hint {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

.r-v2-copy-link__box {
  display: block;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  color: var(--r-color-brand-primary);
  font-family: var(--r-font-family-mono, monospace);
  font-size: var(--r-font-size-sm);
  word-break: break-all;
  user-select: all;
  cursor: text;
}
</style>
