<script setup lang="ts">
// ShowQRCodeDialog — emitter-driven QR for downloading a single ROM from a
// handheld/phone. The qrcode library renders into the canvas directly
// after the dialog opens (nextTick so the canvas is in the DOM).
import { RDialog } from "@v2/lib";
import type { Emitter } from "mitt";
import qrcode from "qrcode";
import { inject, nextTick, onBeforeUnmount, ref } from "vue";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getNintendoDSFiles, getDownloadLink, isNintendoDSFile } from "@/utils";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { colorCanvas, colorOverlay } from "@/v2/tokens";

defineOptions({ inheritAttrs: false });

const { lgAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const canvasRef = ref<HTMLCanvasElement | null>(null);

const openHandler = async (romToView: SimpleRom) => {
  show.value = true;
  rom.value = romToView;

  await nextTick();

  const isNDSFile = isNintendoDSFile(romToView);
  const matchingFiles = getNintendoDSFiles(romToView);

  const downloadLink = getDownloadLink({
    rom: romToView,
    fileIDs: isNDSFile ? [] : [matchingFiles[0].id],
  });

  if (canvasRef.value) {
    qrcode.toCanvas(canvasRef.value, downloadLink, {
      margin: 1,
      width: lgAndUp.value ? 300 : 220,
      color: {
        dark: colorCanvas.bgDeep,
        light: colorOverlay.emphasisBg,
      },
    });
  }
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
      <span>Scan to download</span>
    </template>
    <template #content>
      <div class="r-v2-qr">
        <p v-if="rom" class="r-v2-qr__name" :title="rom.name ?? undefined">
          {{ rom.name }}
        </p>
        <p v-if="rom" class="r-v2-qr__filename" :title="rom.fs_name">
          {{ rom.fs_name }}
        </p>
        <div class="r-v2-qr__canvas-wrap">
          <canvas ref="canvasRef" />
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

.r-v2-qr__canvas-wrap {
  margin: 20px 0px 30px;
  padding: 6px;
  background: var(--r-color-overlay-emphasis-bg);
  border-radius: var(--r-radius-md);
  box-shadow: 0 8px 20px color-mix(in srgb, black 35%, transparent);
  display: grid;
  place-items: center;
}
</style>
