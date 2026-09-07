<script setup lang="ts">
// BarcodeScannerDialog — live-camera barcode scanner. Opens the device
// camera (rear-facing when available), decodes UPC/EAN barcodes with
// ZXing, and emits the decoded value. Purely presentational + camera
// plumbing; the caller owns what to do with the code.
//
// Camera access needs a secure context (HTTPS or localhost); callers gate the
// trigger on that themselves.
import { RBtn, RDialog, RIcon } from "@v2/lib";
import {
  BrowserMultiFormatReader,
  type IScannerControls,
} from "@zxing/browser";
import { BarcodeFormat, DecodeHintType } from "@zxing/library";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "detected", code: string): void;
}>();

const { t } = useI18n();

// Restrict to the retail 1D formats we care about — narrowing the format
// set makes decoding faster and less prone to false positives.
const hints = new Map();
hints.set(DecodeHintType.POSSIBLE_FORMATS, [
  BarcodeFormat.UPC_A,
  BarcodeFormat.UPC_E,
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
]);

const videoRef = ref<HTMLVideoElement | null>(null);
const errorMsg = ref("");

let controls: IScannerControls | null = null;
// Bumped on every start and stop. The await below spans a permission prompt, so
// without it a teardown mid-start would be undone by the controls landing after.
let startToken = 0;

function stopCamera() {
  startToken += 1;
  controls?.stop();
  controls = null;
}

async function startCamera() {
  errorMsg.value = "";
  if (!navigator.mediaDevices?.getUserMedia) {
    errorMsg.value = t("rom.barcode-scan-unsupported");
    return;
  }

  const token = ++startToken;
  try {
    await nextTick();
    const video = videoRef.value;
    if (!video) return;

    const reader = new BrowserMultiFormatReader(hints);
    const started = await reader.decodeFromConstraints(
      { video: { facingMode: "environment" } },
      video,
      (result) => {
        if (!result) return;
        const code = result.getText().trim();
        if (code) onDetected(code);
      },
    );

    if (token !== startToken) {
      started.stop();
      return;
    }
    controls = started;
  } catch (err) {
    const name = (err as { name?: string })?.name;
    errorMsg.value =
      name === "NotAllowedError"
        ? t("rom.barcode-scan-denied")
        : t("rom.barcode-scan-failed");
    stopCamera();
  }
}

function onDetected(code: string) {
  emit("detected", code);
  close();
}

function close() {
  stopCamera();
  emit("update:modelValue", false);
}

// `post` so the initial run lands after mount, when the callers that render
// this lazily behind a `v-if` have already provided the video element.
watch(
  () => props.modelValue,
  (open) => {
    if (open) startCamera();
    else stopCamera();
  },
  { immediate: true, flush: "post" },
);

onBeforeUnmount(stopCamera);
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-barcode-scan"
    :width="480"
    @update:model-value="(v: boolean) => (v ? null : close())"
    @close="close"
  >
    <template #header>
      <span>{{ t("rom.barcode-scan-title") }}</span>
    </template>

    <template #content>
      <div class="r-v2-bsc">
        <div v-if="errorMsg" class="r-v2-bsc__error">
          <RIcon icon="mdi-camera-off" size="20" />
          <span>{{ errorMsg }}</span>
        </div>
        <div v-else class="r-v2-bsc__viewport">
          <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -- live camera preview has no caption track -->
          <video
            ref="videoRef"
            class="r-v2-bsc__video"
            autoplay
            playsinline
            muted
          />
          <div class="r-v2-bsc__reticle" aria-hidden="true" />
        </div>
        <p class="r-v2-bsc__hint">{{ t("rom.barcode-scan-hint") }}</p>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-bsc {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.r-v2-bsc__viewport {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}

.r-v2-bsc__video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* A framing guide so the user knows where to hold the barcode. */
.r-v2-bsc__reticle {
  position: absolute;
  inset: 22% 12%;
  border: 2px solid var(--r-color-brand);
  border-radius: var(--r-radius-sm);
  box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.35);
}

.r-v2-bsc__error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: var(--r-color-fg-secondary);
  background: var(--r-color-bg-elevated);
  border-radius: var(--r-radius-md);
}

.r-v2-bsc__hint {
  margin: 0;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}
</style>
