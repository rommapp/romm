<script setup lang="ts">
// AddPhysicalGameDialog — manually add a game you own physically (cartridge,
// disc, boxed copy) that has no file on disk. The backend stores it as a
// file-less Rom (is_physical=true) and auto-links metadata by name/UPC in a
// single quick scan.
//
// Flow:
//   • Emitter fires `showAddPhysicalGameDialog`; a Platform payload prefills
//     the platform field, null lets the user pick one.
//   • The user enters a game name and/or a UPC, then submits.
//   • POST /roms/physical matches metadata; on success the gallery refreshes
//     if it's showing the same platform.
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import BarcodeScannerDialog from "@/v2/components/shared/BarcodeScannerDialog.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

// Camera scanning needs getUserMedia in a secure context (HTTPS / localhost).
const canScanBarcode =
  typeof navigator !== "undefined" &&
  !!navigator.mediaDevices?.getUserMedia &&
  window.isSecureContext;

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const snackbar = useSnackbar();
const emitter = inject<Emitter<Events>>("emitter");

const platformsStore = storePlatforms();
const { filledPlatforms } = storeToRefs(platformsStore);
const galleryRoms = storeGalleryRoms();

const show = ref(false);
const submitting = ref(false);
const formValid = ref(true);
const platformId = ref<number | null>(null);
const name = ref("");
const upc = ref("");
const scannerOpen = ref(false);

function onBarcodeDetected(code: string) {
  upc.value = code;
}

const canSubmit = computed(
  () => platformId.value != null && (name.value.trim() || upc.value.trim()),
);

const openHandler = (platform: Platform | null) => {
  platformId.value = platform?.id ?? null;
  name.value = "";
  upc.value = "";
  show.value = true;
};
emitter?.on("showAddPhysicalGameDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showAddPhysicalGameDialog", openHandler));

function close() {
  show.value = false;
}

async function submit() {
  if (submitting.value || platformId.value == null) return;
  if (!name.value.trim() && !upc.value.trim()) {
    snackbar.warning(t("rom.physical-name-or-upc-required"), {
      icon: "mdi-information",
    });
    return;
  }

  submitting.value = true;
  try {
    const { data } = await romApi.createPhysicalRom({
      platformId: platformId.value,
      name: name.value.trim() || undefined,
      upc: upc.value.trim() || undefined,
    });
    snackbar.success(t("rom.physical-game-added"), { icon: "mdi-check-bold" });
    show.value = false;

    // Refresh the gallery in place when it's showing this platform.
    if (galleryRoms.currentPlatform?.id === data.platform_id) {
      galleryRoms.invalidateWindows();
      await galleryRoms.fetchInitialMetadata();
    }
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string; detail?: string } };
      message?: string;
    };
    snackbar.error(
      `${t("rom.physical-game-add-failed")}: ${
        e?.response?.data?.msg ||
        e?.response?.data?.detail ||
        e?.message ||
        t("common.unknown-error")
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-cube-outline"
    :width="mdAndUp ? 520 : '95vw'"
    @close="close"
  >
    <template #header>
      <span>{{ t("rom.add-physical-game") }}</span>
    </template>

    <template #content>
      <RForm v-model="formValid" class="r-v2-apg__form" @submit="submit">
        <p class="r-v2-apg__desc">{{ t("rom.add-physical-game-desc") }}</p>

        <PlatformSelect
          v-model="platformId"
          :items="filledPlatforms"
          :label="t('common.platform')"
          :placeholder="t('common.platform')"
          prefix-label="stacked"
          clearable
        />

        <RTextField
          v-model="name"
          :placeholder="t('rom.physical-game-name')"
          prefix-label="stacked"
        >
          <template #prefix-label>
            {{ t("rom.physical-game-name") }}
          </template>
        </RTextField>

        <div class="r-v2-apg__upc-row">
          <RTextField
            v-model="upc"
            class="r-v2-apg__upc-field"
            :placeholder="t('rom.physical-upc')"
            prefix-label="stacked"
            hide-details
          >
            <template #prefix-label>
              {{ t("rom.physical-upc") }}
            </template>
          </RTextField>
          <RBtn
            v-if="canScanBarcode"
            class="r-v2-apg__scan-btn"
            variant="outlined"
            surface
            icon="mdi-barcode-scan"
            :aria-label="t('rom.barcode-scan-title')"
            :tooltip="t('rom.barcode-scan-title')"
            @click="scannerOpen = true"
          />
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="submitting" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        :disabled="!canSubmit || submitting"
        :loading="submitting"
        @click="submit"
      >
        {{ t("common.add") }}
      </RBtn>
    </template>
  </RDialog>

  <BarcodeScannerDialog v-model="scannerOpen" @detected="onBarcodeDetected" />
</template>

<style scoped>
.r-v2-apg__form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-apg__desc {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-apg__upc-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.r-v2-apg__upc-field {
  flex: 1 1 auto;
}

.r-v2-apg__scan-btn {
  flex: 0 0 auto;
}
</style>
