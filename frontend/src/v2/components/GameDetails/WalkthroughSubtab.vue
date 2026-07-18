<script setup lang="ts">
// WalkthroughSubtab — the Media tab's Walkthrough panel. Surfaces
// walkthrough-category files (uploaded, or fetched from a GameFAQs guide URL),
// picking the viewer (PDF / Markdown / Text) by extension. Mirrors
// ManualSubtab's chrome, plus an "add from GameFAQs URL" affordance.
import { RBtn, RDropzone, RSelect, RTextField } from "@v2/lib";
import axios from "axios";
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
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

type ViewerKind = "pdf" | "md" | "text";
type WalkthroughEntry = {
  id: string;
  fileId: number;
  label: string;
  url: string;
  kind: ViewerKind;
};

const props = defineProps<{ rom: DetailedRom }>();
const snackbar = useSnackbar();
const confirm = useConfirm();
const romsStore = storeRoms();
const { t } = useI18n();

function kindFor(name: string): ViewerKind {
  if (/\.md$/i.test(name)) return "md";
  if (/\.(txt|html?|htm)$/i.test(name)) return "text";
  return "pdf";
}

const entries = computed<WalkthroughEntry[]>(() => {
  const cacheBust = encodeURIComponent(props.rom.updated_at);
  const out: WalkthroughEntry[] = [];
  for (const file of props.rom.files ?? []) {
    if (file.category !== "walkthrough") continue;
    out.push({
      id: `file-${file.id}`,
      fileId: file.id,
      // Prefer the scraped guide title when present, else the file name.
      label: file.doc_meta?.title ?? file.file_name.replace(/\.[^.]+$/, ""),
      url: `/api/roms/${file.id}/files/content/${encodeURIComponent(
        file.file_name,
      )}?v=${cacheBust}`,
      kind: kindFor(file.file_name),
    });
  }
  return out;
});

const selectedId = ref<string>("");
let previousIds = new Set<string>();

watch(
  entries,
  (list) => {
    const currentIds = new Set(list.map((e) => e.id));
    if (list.length === 0) {
      selectedId.value = "";
    } else {
      const added = list.filter((e) => !previousIds.has(e.id));
      if (added.length > 0 && previousIds.size > 0) {
        selectedId.value = added[added.length - 1].id;
      } else if (!list.some((e) => e.id === selectedId.value)) {
        selectedId.value = list[0].id;
      }
    }
    previousIds = currentIds;
  },
  { immediate: true },
);

const selected = computed(() =>
  entries.value.find((e) => e.id === selectedId.value),
);
const selectItems = computed(() =>
  entries.value.map((e) => ({ title: e.label, value: e.id })),
);

async function refreshRom() {
  try {
    const { data } = await romApi.getRom({ romId: props.rom.id });
    romsStore.currentRom = data;
    romsStore.update(data);
  } catch (error) {
    console.error(error);
  }
}

// ---------- Single-file -> folder conversion ----------
async function confirmFolderConversionIfNeeded(): Promise<boolean> {
  if (!props.rom.has_simple_single_file) return true;
  return confirm({
    title: t("rom.convert-to-folder-title"),
    body: t("rom.convert-to-folder-body"),
    tone: "warning",
  });
}

// ---------- Upload ----------
const walkthroughDz = ref<InstanceType<typeof RDropzone> | null>(null);

async function handleFiles(files: File[]) {
  if (files.length === 0) return;
  if (!(await confirmFolderConversionIfNeeded())) return;
  const responses = await romApi.uploadWalkthroughFiles({
    romId: props.rom.id,
    filesToUpload: files,
  });
  const ok = responses.filter((r) => r.status === "fulfilled").length;
  if (ok > 0) {
    await refreshRom();
    snackbar.success(t("rom.walkthrough-added"), { icon: "mdi-check-bold" });
  } else {
    snackbar.error(
      t("rom.walkthrough-add-failed", { error: t("common.unknown-error") }),
      { icon: "mdi-close-circle" },
    );
  }
}

// ---------- Add from GameFAQs URL ----------
const gamefaqsUrl = ref("");
const addingUrl = ref(false);

async function addFromUrl() {
  const url = gamefaqsUrl.value.trim();
  if (!url || addingUrl.value) return;
  if (!(await confirmFolderConversionIfNeeded())) return;
  addingUrl.value = true;
  try {
    await romApi.addGamefaqsWalkthrough({ romId: props.rom.id, url });
    gamefaqsUrl.value = "";
    await refreshRom();
    snackbar.success(t("rom.walkthrough-added"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.walkthrough-add-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    addingUrl.value = false;
  }
}

// ---------- Delete ----------
async function requestDelete() {
  const entry = selected.value;
  if (!entry) return;
  const ok = await confirm({
    title: t("rom.walkthrough"),
    body: t("rom.delete-track-body-named", { name: entry.label }),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await romApi.deleteWalkthroughFile({
      romId: props.rom.id,
      fileId: entry.fileId,
    });
    await refreshRom();
    snackbar.success(t("rom.walkthrough-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.walkthrough-remove-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  }
}
</script>

<template>
  <div class="r-v2-wt">
    <header class="r-v2-wt__head">
      <RSelect
        v-if="entries.length > 1"
        v-model="selectedId"
        :items="selectItems"
        density="compact"
        variant="outlined"
        hide-details
        class="r-v2-wt__select"
      />
      <span class="r-v2-wt__spacer" />
      <div class="r-v2-wt__url">
        <RTextField
          v-model="gamefaqsUrl"
          :placeholder="t('rom.walkthrough-url-label')"
          density="compact"
          variant="outlined"
          hide-details
          @keyup.enter="addFromUrl"
        />
        <RBtn
          variant="outlined"
          size="small"
          prepend-icon="mdi-link-variant"
          :loading="addingUrl"
          :disabled="addingUrl || !gamefaqsUrl.trim()"
          @click="addFromUrl"
        >
          {{ t("rom.add-walkthrough-from-url") }}
        </RBtn>
      </div>
    </header>

    <RDropzone
      v-if="entries.length === 0"
      :title="t('rom.walkthrough-empty')"
      :hint="t('common.dropzone-hint')"
      :active-title="t('common.dropzone-drag-over')"
      :input-label="t('rom.upload-walkthrough')"
      accept="application/pdf,.md,.txt,.html,.htm"
      multiple
      @files="handleFiles"
    />

    <RDropzone
      v-if="selected"
      ref="walkthroughDz"
      overlay
      class="r-v2-wt__fill"
      :release-label="t('common.dropzone-drag-over')"
      :input-label="t('rom.upload-walkthrough')"
      accept="application/pdf,.md,.txt,.html,.htm"
      multiple
      @files="handleFiles"
    >
      <div class="r-v2-wt__viewer">
        <MarkdownViewer
          v-if="selected.kind === 'md'"
          :key="`${selected.id}-${rom.updated_at}-md`"
          :url="selected.url"
          deletable
          @delete="requestDelete"
        />
        <TextViewer
          v-else-if="selected.kind === 'text'"
          :key="`${selected.id}-${rom.updated_at}-txt`"
          :url="selected.url"
          :rom-id="rom.id"
          :file-id="selected.fileId"
          deletable
          @delete="requestDelete"
        />
        <PdfViewer
          v-else
          :key="`${selected.id}-${rom.updated_at}-pdf`"
          :pdf-url="selected.url"
          deletable
          @delete="requestDelete"
        />
      </div>
    </RDropzone>

    <div v-if="entries.length > 0">
      <RBtn
        block
        variant="outlined"
        size="small"
        prepend-icon="mdi-cloud-upload-outline"
        @click="walkthroughDz?.open()"
      >
        {{ t("common.upload") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-wt {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-v2-wt__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.r-v2-wt__spacer {
  flex: 1;
}
.r-v2-wt__select {
  max-width: 360px;
  min-width: 200px;
}
.r-v2-wt__url {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 260px;
}
.r-v2-wt__fill {
  flex: 1;
  min-height: 30rem;
  display: flex;
  flex-direction: column;
}
.r-v2-wt__viewer {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}
</style>
