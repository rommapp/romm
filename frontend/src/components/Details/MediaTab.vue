<script setup lang="ts">
import axios from "axios";
import type { Emitter } from "mitt";
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

const PdfViewer = defineAsyncComponent(
  () => import("@/components/Details/PDFViewer.vue"),
);
const SoundtrackPlayer = defineAsyncComponent(
  () => import("@/components/Details/SoundtrackPlayer.vue"),
);

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

const props = defineProps<{ rom: DetailedRom }>();
const { t } = useI18n();
const { mdAndDown } = useDisplay();
const route = useRoute();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();
const uploadStore = storeUpload();

const validSubtabs = ["manual", "soundtrack"] as const;
type Subtab = (typeof validSubtabs)[number];

const subTab = ref<Subtab>(
  validSubtabs.includes(route.query.subtab as Subtab)
    ? (route.query.subtab as Subtab)
    : "manual",
);

watch(subTab, (newSubtab) => {
  if (route.query.subtab !== newSubtab) {
    router.replace({
      path: route.path,
      query: { ...route.query, subtab: newSubtab },
    });
  }
});

watch(
  () => route.query.subtab,
  (newSubtab) => {
    if (newSubtab && validSubtabs.includes(newSubtab as Subtab)) {
      subTab.value = newSubtab as Subtab;
    }
  },
  { immediate: true },
);

watch(
  () => route.query.tab,
  (newTab) => {
    if (newTab !== "media" && route.query.subtab) {
      const rest = { ...route.query };
      delete rest.subtab;
      router.replace({ path: route.path, query: rest });
    }
  },
);

type ManualEntry = {
  id: string;
  label: string;
  url: string;
  isPrimary: boolean;
};

const manualEntries = computed<ManualEntry[]>(() => {
  const entries: ManualEntry[] = [];
  const cacheBust = encodeURIComponent(props.rom.updated_at);
  if (props.rom.has_manual && props.rom.path_manual) {
    entries.push({
      id: "primary",
      label: t("rom.scraped-manual"),
      url: `${FRONTEND_RESOURCES_PATH}/${props.rom.path_manual}?v=${cacheBust}`,
      isPrimary: true,
    });
  }
  for (const file of props.rom.files) {
    if (file.category === "manual") {
      entries.push({
        id: `file-${file.id}`,
        label: file.file_name.replace(/\.[^.]+$/, ""),
        url: `/api/roms/${file.id}/files/content/${encodeURIComponent(file.file_name)}?v=${cacheBust}`,
        isPrimary: false,
      });
    }
  }
  return entries;
});

const selectedManualId = ref<string>("");
let previousManualIds = new Set<string>();

watch(
  manualEntries,
  (entries) => {
    const currentIds = new Set(entries.map((e) => e.id));
    if (entries.length === 0) {
      selectedManualId.value = "";
    } else {
      // If a new entry appeared after a previous snapshot, auto-select it so
      // the user lands on the manual they just uploaded.
      const added = entries.filter((e) => !previousManualIds.has(e.id));
      if (added.length > 0 && previousManualIds.size > 0) {
        selectedManualId.value = added[added.length - 1].id;
      } else if (!entries.some((e) => e.id === selectedManualId.value)) {
        selectedManualId.value = entries[0].id;
      }
    }
    previousManualIds = currentIds;
  },
  { immediate: true },
);

const selectedManual = computed(() =>
  manualEntries.value.find((e) => e.id === selectedManualId.value),
);

const soundtrackSupported = computed(() => !props.rom.has_simple_single_file);

const manualUploadInput = ref<HTMLInputElement | null>(null);
const soundtrackUploadInput = ref<HTMLInputElement | null>(null);
const redownloadingManual = ref(false);

function triggerManualUpload() {
  manualUploadInput.value?.click();
}

function triggerSoundtrackUpload() {
  soundtrackUploadInput.value?.click();
}

async function refreshRom() {
  try {
    const { data } = await romApi.getRom({ romId: props.rom.id });
    romsStore.currentRom = data;
    romsStore.update(data);
  } catch (error) {
    console.error(error);
  }
}

function onManualUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (files.length === 0) return;

  emitter?.emit("showManualUploadTargetDialog", {
    rom: props.rom,
    files,
  });
}

async function onSoundtrackUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (files.length === 0) return;

  const responses = await romApi.uploadSoundtracks({
    romId: props.rom.id,
    filesToUpload: files,
  });
  input.value = "";

  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) {
    uploadStore.reset();
  }

  if (successful > 0) {
    emitter?.emit("snackbarShow", {
      msg: t("rom.soundtracks-upload-success", { count: successful, failed }),
      icon: "mdi-check-bold",
      color: "green",
      timeout: 3000,
    });
    await refreshRom();
  } else {
    emitter?.emit("snackbarShow", {
      msg: t("rom.soundtracks-upload-skipped"),
      icon: "mdi-close-circle",
      color: "orange",
      timeout: 5000,
    });
  }
}

async function redownloadManual() {
  if (redownloadingManual.value) return;
  redownloadingManual.value = true;
  try {
    await romApi.redownloadManual({ romId: props.rom.id });
    await refreshRom();
    emitter?.emit("snackbarShow", {
      msg: t("rom.manual-redownloaded"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: unknown) {
    emitter?.emit("snackbarShow", {
      msg: t("rom.manual-redownload-failed", { error: errorMessage(error) }),
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    redownloadingManual.value = false;
  }
}

function requestDeleteManual() {
  const entry = selectedManual.value;
  if (!entry) return;
  emitter?.emit("showDeleteManualDialog", {
    rom: props.rom,
    isPrimary: entry.isPrimary,
    fileId: entry.isPrimary
      ? undefined
      : Number(entry.id.replace(/^file-/, "")),
  });
}

async function deleteSoundtrack(fileId: number) {
  try {
    await romApi.removeSoundtrack({ romId: props.rom.id, fileId });
    await refreshRom();
    emitter?.emit("snackbarShow", {
      msg: t("rom.soundtrack-removed"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: unknown) {
    emitter?.emit("snackbarShow", {
      msg: t("rom.soundtrack-remove-failed", { error: errorMessage(error) }),
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}
</script>

<template>
  <input
    ref="manualUploadInput"
    type="file"
    accept="application/pdf"
    multiple
    class="d-none"
    :aria-label="t('rom.upload-manual')"
    @change="onManualUpload"
  />
  <input
    ref="soundtrackUploadInput"
    type="file"
    accept="audio/*,.flac,.opus"
    multiple
    class="d-none"
    :aria-label="t('rom.upload-soundtrack')"
    @change="onSoundtrackUpload"
  />
  <v-row no-gutters>
    <v-col cols="12" lg="auto">
      <v-tabs
        v-model="subTab"
        :direction="mdAndDown ? 'horizontal' : 'vertical'"
        :align-tabs="mdAndDown ? 'center' : 'start'"
        slider-color="secondary"
        class="mr-4 mt-2"
        selected-class="bg-toplayer"
      >
        <v-tab
          prepend-icon="mdi-book-open-page-variant-outline"
          class="rounded text-caption"
          value="manual"
        >
          {{ t("rom.manual") }}
        </v-tab>
        <v-tab
          prepend-icon="mdi-music"
          class="rounded text-caption"
          value="soundtrack"
        >
          {{ t("rom.soundtrack") }}
        </v-tab>
      </v-tabs>
    </v-col>
    <v-col>
      <v-tabs-window v-model="subTab">
        <v-tabs-window-item value="manual">
          <div v-if="manualEntries.length === 0" class="pa-6 text-center">
            <v-icon size="48" class="mb-2 text-medium-emphasis">
              mdi-book-open-page-variant-outline
            </v-icon>
            <div class="text-body-2 text-medium-emphasis mb-3">
              {{ t("rom.no-manual") }}
            </div>
            <div class="d-flex justify-center ga-2">
              <v-btn
                prepend-icon="mdi-cloud-upload-outline"
                variant="tonal"
                @click="triggerManualUpload"
              >
                {{ t("rom.upload-manual") }}
              </v-btn>
              <v-btn
                v-if="rom.url_manual"
                prepend-icon="mdi-cloud-download-outline"
                variant="tonal"
                :loading="redownloadingManual"
                :disabled="redownloadingManual"
                @click="redownloadManual"
              >
                {{ t("rom.redownload-manual") }}
              </v-btn>
            </div>
          </div>
          <div v-else>
            <div class="d-flex align-center mb-2 ga-2">
              <v-select
                v-if="manualEntries.length > 1"
                v-model="selectedManualId"
                :items="manualEntries"
                item-title="label"
                item-value="id"
                density="compact"
                hide-details
                variant="outlined"
                class="flex-grow-1"
              />
              <v-spacer v-else />
              <v-btn
                prepend-icon="mdi-cloud-upload-outline"
                variant="tonal"
                size="small"
                @click="triggerManualUpload"
              >
                {{ t("rom.upload-manual") }}
              </v-btn>
              <v-btn
                v-if="rom.url_manual"
                prepend-icon="mdi-cloud-download-outline"
                variant="tonal"
                size="small"
                :loading="redownloadingManual"
                :disabled="redownloadingManual"
                @click="redownloadManual"
              >
                {{ t("rom.redownload-manual") }}
              </v-btn>
              <v-btn
                v-if="selectedManual"
                prepend-icon="mdi-delete"
                variant="tonal"
                size="small"
                class="text-romm-red"
                @click="requestDeleteManual"
              >
                {{ t("rom.delete") }}
              </v-btn>
            </div>
            <PdfViewer
              v-if="selectedManual"
              :key="`${selectedManual.id}-${rom.updated_at}`"
              :pdf-url="selectedManual.url"
            />
          </div>
        </v-tabs-window-item>
        <v-tabs-window-item value="soundtrack">
          <div v-if="!soundtrackSupported" class="pa-6 text-center">
            <v-icon size="48" class="mb-2 text-medium-emphasis">
              mdi-music-off-outline
            </v-icon>
            <div class="text-body-2 text-medium-emphasis">
              {{ t("rom.soundtrack-folder-only") }}
            </div>
          </div>
          <div v-else-if="!rom.has_soundtrack" class="pa-6 text-center">
            <v-icon size="48" class="mb-2 text-medium-emphasis">
              mdi-music-note-outline
            </v-icon>
            <div class="text-body-2 text-medium-emphasis mb-3">
              {{ t("rom.no-soundtrack") }}
            </div>
            <v-btn
              prepend-icon="mdi-cloud-upload-outline"
              variant="tonal"
              @click="triggerSoundtrackUpload"
            >
              {{ t("rom.upload-soundtrack") }}
            </v-btn>
          </div>
          <SoundtrackPlayer
            v-else
            :rom="rom"
            @upload-tracks="triggerSoundtrackUpload"
            @delete-track="deleteSoundtrack"
          />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>
