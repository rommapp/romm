<script setup lang="ts">
// ManualSubtab — the Media tab's Manual panel. Surfaces the scraped primary
// manual plus any manual-category files sitting in the ROM folder, picking the
// viewer (PDF or Markdown) by extension. An entry selector appears when more
// than one manual exists. The panel doubles as a drag-and-drop upload target.
//
// Like ArtworkSubtab, it owns its own scroll (flex column filling the Media
// tab's content height) so the viewer keeps its internal scroll and switching
// subtabs never forces an outer scrollbar.
import { RBtn, RDropzone, RSelect } from "@v2/lib";
import axios from "axios";
import type { Emitter } from "mitt";
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const PdfViewer = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/PdfViewer.vue"),
);
const MarkdownViewer = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/MarkdownViewer.vue"),
);
const TextViewer = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/TextViewer.vue"),
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
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();
const romsStore = storeRoms();
const { t } = useI18n();

// ---------- Manual entries ----------
type ManualEntry = {
  id: string;
  label: string;
  url: string;
  isPrimary: boolean;
  // Manuals can be PDF, Markdown, or plain text; the viewer is picked by
  // extension.
  kind: "pdf" | "md" | "text";
};

const kindFor = (name: string): ManualEntry["kind"] => {
  if (/\.md$/i.test(name)) return "md";
  if (/\.(txt|html?|htm)$/i.test(name)) return "text";
  return "pdf";
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
      kind: kindFor(props.rom.path_manual),
    });
  }
  for (const file of props.rom.files ?? []) {
    if (file.category === "manual") {
      entries.push({
        id: `file-${file.id}`,
        label: file.file_name.replace(/\.[^.]+$/, ""),
        url: `/api/roms/${file.id}/files/content/${encodeURIComponent(
          file.file_name,
        )}?v=${cacheBust}`,
        isPrimary: false,
        kind: kindFor(file.file_name),
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
      // If a new entry appears after a prior snapshot, select it so the user
      // lands on the manual they just uploaded.
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
const manualItems = computed(() =>
  manualEntries.value.map((e) => ({ title: e.label, value: e.id })),
);

// ---------- Single-file -> folder conversion ----------
// Manuals live inside the ROM folder, so uploading one to a single-file ROM
// promotes it to a folder ROM in place (the backend does this automatically on
// upload). Warn first since it is not reversible.
async function confirmFolderConversionIfNeeded(): Promise<boolean> {
  if (!props.rom.has_simple_single_file) return true;
  return confirm({
    title: t("rom.convert-to-folder-title"),
    body: t("rom.convert-to-folder-body"),
    tone: "warning",
  });
}

// ---------- Upload / refresh plumbing ----------
// The filled viewer is wrapped in an overlay RDropzone (drag files onto the
// manual to add another); the header's Upload button opens its picker.
const manualDz = ref<InstanceType<typeof RDropzone> | null>(null);
const redownloadingManual = ref(false);

async function refreshRom() {
  try {
    const { data } = await romApi.getRom({ romId: props.rom.id });
    romsStore.currentRom = data;
    romsStore.update(data);
  } catch (error) {
    console.error(error);
  }
}

// Manual upload routes through the target-selection dialog (mounted in
// AppLayout): the user picks which platform/folder the manual belongs to, so
// we hand off rather than uploading inline.
async function handleManualFiles(files: File[]) {
  if (files.length === 0) return;
  if (!(await confirmFolderConversionIfNeeded())) return;
  emitter?.emit("showManualUploadTargetDialog", { rom: props.rom, files });
}

async function redownloadManual() {
  if (redownloadingManual.value) return;
  redownloadingManual.value = true;
  try {
    await romApi.redownloadManual({ romId: props.rom.id });
    await refreshRom();
    snackbar.success(t("rom.manual-redownloaded"), {
      icon: "mdi-check-bold",
    });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.manual-redownload-failed", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
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
</script>

<template>
  <div class="r-v2-manual">
    <!-- The subtab label in the sidebar already names the section, so the
         header skips a redundant title and just hosts the entry selector
         (when multiple). -->
    <header v-if="manualEntries.length > 1" class="r-v2-manual__head">
      <RSelect
        v-model="selectedManualId"
        :items="manualItems"
        density="compact"
        variant="outlined"
        hide-details
        class="r-v2-manual__select"
      />
    </header>

    <RDropzone
      v-if="manualEntries.length === 0"
      :title="t('rom.manual-empty')"
      :hint="t('common.dropzone-hint')"
      :active-title="t('common.dropzone-drag-over')"
      :input-label="t('rom.upload-manual')"
      accept="application/pdf,.md,.txt"
      multiple
      @files="handleManualFiles"
    >
      <template v-if="rom.url_manual" #actions>
        <RBtn
          variant="outlined"
          prepend-icon="mdi-cloud-download-outline"
          :loading="redownloadingManual"
          :disabled="redownloadingManual"
          @click.stop="redownloadManual"
        >
          {{ t("rom.redownload") }}
        </RBtn>
      </template>
    </RDropzone>

    <RDropzone
      v-if="selectedManual"
      ref="manualDz"
      overlay
      class="r-v2-manual__fill"
      :release-label="t('common.dropzone-drag-over')"
      :input-label="t('rom.upload-manual')"
      accept="application/pdf,.md,.txt"
      multiple
      @files="handleManualFiles"
    >
      <div class="r-v2-manual__viewer">
        <MarkdownViewer
          v-if="selectedManual.kind === 'md'"
          :key="`${selectedManual.id}-${rom.updated_at}-md`"
          :url="selectedManual.url"
          deletable
          :redownloadable="!!rom.url_manual"
          :redownloading="redownloadingManual"
          @delete="requestDeleteManual"
          @redownload="redownloadManual"
        />
        <TextViewer
          v-else-if="selectedManual.kind === 'text'"
          :key="`${selectedManual.id}-${rom.updated_at}-txt`"
          :url="selectedManual.url"
          deletable
          @delete="requestDeleteManual"
        />
        <PdfViewer
          v-else
          :key="`${selectedManual.id}-${rom.updated_at}-pdf`"
          :pdf-url="selectedManual.url"
          deletable
          :redownloadable="!!rom.url_manual"
          :redownloading="redownloadingManual"
          @delete="requestDeleteManual"
          @redownload="redownloadManual"
        />
      </div>
    </RDropzone>

    <div v-if="manualEntries.length > 0">
      <RBtn
        block
        variant="outlined"
        size="small"
        prepend-icon="mdi-cloud-upload-outline"
        @click="manualDz?.open()"
      >
        {{ t("common.upload") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-manual {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}

/* Header — hosts the manual entry selector (when more than one manual) and
   the Upload button, pushed to the right. */
.r-v2-manual__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

/* Manual entry selector — capped width so it doesn't stretch to fill the
   row. */
.r-v2-manual__select {
  max-width: 360px;
  min-width: 200px;
  flex-shrink: 1;
}

/* Overlay-mode RDropzone wrapping the viewer must fill the panel height so
   the inner viewer can stretch to 100%. The min-height keeps the flex chain
   from collapsing the viewer to zero. */
.r-v2-manual__fill {
  flex: 1;
  min-height: 30rem;
  display: flex;
  flex-direction: column;
}

/* Viewer — fills the available panel height so the inner PDF / Markdown uses
   100% and only its own scroll triggers. */
.r-v2-manual__viewer {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}
</style>
