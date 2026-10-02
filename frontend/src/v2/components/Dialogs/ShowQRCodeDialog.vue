<script setup lang="ts">
// ShowQRCodeDialog: emitter-driven QR for downloading a single ROM from a
// handheld/phone.
import { RDialog } from "@v2/lib";
import { useQRCode } from "@vueuse/integrations/useQRCode";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getNintendoDSFiles, getDownloadLink, isNintendoDSFile } from "@/utils";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { colorCanvas, colorOverlay } from "@/v2/tokens";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { lgAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const emitter = inject<Emitter<Events>>("emitter");

const downloadLink = computed(() => {
  if (!rom.value) return "";
  const isNDSFile = isNintendoDSFile(rom.value);
  const matchingFiles = getNintendoDSFiles(rom.value);
  return getDownloadLink({
    rom: rom.value,
    fileIDs: isNDSFile ? [] : [matchingFiles[0].id],
  });
});

// Rendered at 2x the largest display size so it stays sharp on HiDPI screens.
const qrCode = useQRCode(downloadLink, {
  margin: 1,
  width: 600,
  color: {
    dark: colorCanvas.bgDeep,
    light: colorOverlay.emphasisBg,
  },
});
// useQRCode keeps the previous image until the new one resolves; drop it so
// the next ROM never briefly shows the last ROM's code.
watch(downloadLink, () => (qrCode.value = ""));
const qrSize = computed(() => (lgAndUp.value ? 300 : 220));

const openHandler = (romToView: SimpleRom) => {
  show.value = true;
  rom.value = romToView;
};
emitter?.on("showQRCodeDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showQRCodeDialog", openHandler));

function closeDialog() {
  show.value = false;
  rom.value = null;
}
</script>

<template>
  <RDialog v-model="show" icon="mdi-qrcode" width="380" @close="closeDialog">
    <template #header>
      <span>{{ t("rom.qr-scan-to-download") }}</span>
    </template>
    <template #content>
      <div class="r-v2-qr">
        <p v-if="rom" class="r-v2-qr__name" :title="rom.name ?? undefined">
          {{ rom.name }}
        </p>
        <p v-if="rom" class="r-v2-qr__filename" :title="rom.fs_name">
          {{ rom.fs_name }}
        </p>
        <div
          class="r-v2-qr__code-wrap"
          :style="{ width: `${qrSize}px`, height: `${qrSize}px` }"
        >
          <img
            v-if="qrCode"
            :src="qrCode"
            :alt="t('rom.qr-scan-to-download')"
            class="r-v2-qr__code"
          />
        </div>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px;
}

.r-v2-qr__name {
  margin: 0;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

.r-v2-qr__filename {
  margin: 0;
  font-size: 11px;
  color: var(--r-color-brand-primary);
  font-family: var(--r-font-family-mono, monospace);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

.r-v2-qr__code-wrap {
  box-sizing: content-box;
  margin: 20px 0px 0px;
  padding: 6px;
  background: var(--r-color-overlay-emphasis-bg);
  border-radius: var(--r-radius-md);
  box-shadow: 0 8px 20px color-mix(in srgb, black 35%, transparent);
  display: grid;
  place-items: center;
}

.r-v2-qr__code {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
