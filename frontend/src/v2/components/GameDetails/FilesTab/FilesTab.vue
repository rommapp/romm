<script setup lang="ts">
// FilesTab — browse + interact with the individual files that make up
// a (potentially multi-file) ROM.
//
// Layout mirrors ScreenshotsSubtab / SaveDataTab / MediaTab: a vertical
// subtab list on the left (navigation only — no inline action panel),
// and a content column on the right with a section header that hosts
// the Upload button plus a Patch button (multi-file ROMs only). Bulk
// download / copy-link affordances live in the selection toolbar
// instead — pair them with select-all.
//
// Grouping is **folder-based**: every direct subfolder of the ROM
// becomes its own subtab, plus a "Root" subtab for files sitting
// directly under the ROM path. Folder names matching a known
// `RomFileCategory` (manual, soundtrack, dlc, update, …) inherit the
// category icon + label so detected folders read consistently;
// everything else falls back to a generic folder icon and the raw
// folder name. Per-file `category` metadata is still shown as a chip
// inside each row.
//
// Section header (per active subtab):
//   * Upload: the active subtab supplies the destination folder; "All
//     files" has none, so the dialog asks for one.
//
// Content column:
//   * Section header (Upload + Patch)
//   * ROM-info card (size, revision, ROM-level hashes — click to copy)
//   * Selection toolbar (select-all + per-selection Download / Copy-link
//     — also the path for "download everything in this subtab": select
//     all then act).
//   * One row per file with checkbox, relative path, category chip,
//     size, per-file hashes (click to copy), and per-row Download +
//     Copy-link buttons.
//
// Selected files in the Files tab can be deleted by users with the
// `rom.delete` permission. Each file is removed from disk and the DB
// row is dropped via `DELETE /roms/{rom_id}/files/{file_id}`.
import { RBtn, RCheckbox, REmptyState, RIcon, RTooltip } from "@v2/lib";
import axios from "axios";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type {
  DetailedRomSchema,
  RomFileCategory,
  RomFileSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import storeUpload from "@/stores/upload";
import { getDownloadLink } from "@/utils";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";
import FileRow from "./FileRow.vue";
import FilesSummary from "./FilesSummary.vue";
import UploadFilesDialog, {
  type UploadFolderOption,
} from "./UploadFilesDialog.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const route = useRoute();
const router = useRouter();
const romsStore = storeRoms();
const { refetchRom } = useRomSync();

const canUpload = useCan("rom.upload");
const hasDeleteGrant = useCan("rom.delete");
// `DELETE /roms/{id}/files/{file_id}` gates on ROMS_WRITE
const canDelete = computed(() => hasDeleteGrant.value && canUpload.value);

// ---------- Category metadata ----------
// Drives per-file category chips (one per `RomFileCategory` enum
// value). Folder→icon resolution lives in `FOLDER_META` below — it
// extends this with plural names and a couple of well-known folders
// (e.g. `screenshots/`) that aren't backend categories.
const CATEGORY_META = computed<
  Record<RomFileCategory, { label: string; icon: string }>
>(() => ({
  game: { label: t("rom.category-game"), icon: "mdi-gamepad-variant-outline" },
  dlc: { label: t("rom.category-dlc"), icon: "mdi-puzzle-outline" },
  update: { label: t("rom.category-update"), icon: "mdi-update" },
  patch: { label: t("rom.category-patch"), icon: "mdi-bandage" },
  mod: { label: t("rom.category-mod"), icon: "mdi-tools" },
  hack: { label: t("rom.category-hack"), icon: "mdi-pencil-ruler" },
  translation: {
    label: t("rom.category-translation"),
    icon: "mdi-translate",
  },
  demo: { label: t("rom.category-demo"), icon: "mdi-flask-outline" },
  prototype: { label: t("rom.category-prototype"), icon: "mdi-test-tube" },
  cheat: { label: t("rom.category-cheat"), icon: "mdi-incognito" },
  manual: {
    label: t("rom.manual"),
    icon: "mdi-book-open-page-variant-outline",
  },
  walkthrough: {
    label: t("rom.walkthrough"),
    icon: "mdi-map-legend",
  },
  soundtrack: {
    label: t("rom.soundtrack"),
    icon: "mdi-music-note-outline",
  },
  screenshot: {
    label: t("rom.screenshots"),
    icon: "mdi-image-multiple-outline",
  },
}));

// Folder-name → label/icon map. Includes both singular and plural
// forms (the backend matches either, e.g. `cheats/` and `cheat/`
// both classify files as `cheat`), plus a few well-known folders
// that aren't backend categories but deserve a dedicated icon
// (`screenshots/`). Folders not listed here fall back to the
// generic folder icon and keep their on-disk casing as the label.
interface FolderMeta {
  label: string;
  icon: string;
}
const FOLDER_META = computed<Record<string, FolderMeta>>(() => {
  const c = CATEGORY_META.value;
  return {
    // Backend categories — singular and plural variants.
    game: c.game,
    games: c.game,
    dlc: c.dlc,
    dlcs: c.dlc,
    update: c.update,
    updates: c.update,
    patch: c.patch,
    patches: c.patch,
    mod: c.mod,
    mods: c.mod,
    hack: c.hack,
    hacks: c.hack,
    translation: c.translation,
    translations: c.translation,
    demo: c.demo,
    demos: c.demo,
    prototype: c.prototype,
    prototypes: c.prototype,
    cheat: c.cheat,
    cheats: c.cheat,
    manual: c.manual,
    manuals: c.manual,
    walkthrough: c.walkthrough,
    walkthroughs: c.walkthrough,
    soundtrack: c.soundtrack,
    soundtracks: c.soundtrack,
    // Non-category folders that conventionally appear in ROM directories.
    screenshot: {
      label: t("rom.screenshots"),
      icon: "mdi-image-multiple-outline",
    },
    screenshots: {
      label: t("rom.screenshots"),
      icon: "mdi-image-multiple-outline",
    },
  };
});

const ROOT = "__root__" as const;
type Subtab = "all" | typeof ROOT | string;

// ---------- File ordering + folder extraction ----------
// Sort by relative path so multi-disc / nested layouts stay stable
// across re-renders.
const files = computed<RomFileSchema[]>(() => {
  const arr = [...(props.rom.files ?? [])];
  arr.sort((a, b) => relativePath(a).localeCompare(relativePath(b)));
  return arr;
});

// Resolved once per listing: the sort comparator, the folder grouping and
// every row read the same path, and the template re-runs on any selection.
const relativePaths = computed(() => {
  const paths = new Map<number, string>();
  for (const file of props.rom.files ?? []) {
    paths.set(
      file.id,
      file.full_path.replace(props.rom.full_path, "").replace(/^\//, "") ||
        file.file_name,
    );
  }
  return paths;
});

function relativePath(file: RomFileSchema): string {
  return relativePaths.value.get(file.id) ?? file.file_name;
}

// Path rendered in each row. Inside a folder subtab the folder name is
// already the subtab title — strip the prefix so rows lead with the
// filename. The full relative path stays available via `relativePath`
// for aria-labels / hover titles.
function displayPath(file: RomFileSchema): string {
  if (subTab.value === "all") return relativePath(file);
  const folder = fileFolder(file);
  if (folder === ROOT) return relativePath(file);
  const rel = relativePath(file);
  const prefix = `${folder}/`;
  return rel.startsWith(prefix) ? rel.slice(prefix.length) : rel;
}

// First path segment of a file's relative path. Files sitting directly
// under the ROM root get the sentinel `ROOT` key so they collapse into
// a single "Root" subtab.
function fileFolder(file: RomFileSchema): string {
  const rel = relativePath(file);
  const slash = rel.indexOf("/");
  if (slash < 0) return ROOT;
  return rel.slice(0, slash);
}

const filesByFolder = computed(() => {
  const map = new Map<string, RomFileSchema[]>();
  for (const f of files.value) {
    const key = fileFolder(f);
    const bucket = map.get(key);
    if (bucket) bucket.push(f);
    else map.set(key, [f]);
  }
  return map;
});

// Resolve a folder key to its display metadata. Folder names matching
// a known entry in `FOLDER_META` (case-insensitive, singular or
// plural) inherit a dedicated label + icon; otherwise fall back to a
// generic folder icon and the raw folder name (preserving the on-disk
// casing).
function folderMeta(folder: string): FolderMeta | null {
  return FOLDER_META.value[folder.toLowerCase()] ?? null;
}

function folderLabel(folder: string): string {
  if (folder === ROOT) return t("rom.folder-root");
  return folderMeta(folder)?.label ?? folder;
}

function folderIcon(folder: string): string {
  if (folder === ROOT) return "mdi-folder-home-outline";
  return folderMeta(folder)?.icon ?? "mdi-folder-outline";
}

interface SubtabDef {
  id: Subtab;
  label: string;
  icon: string;
  count: number;
}

const subtabDefs = computed<SubtabDef[]>(() => {
  const out: SubtabDef[] = [
    {
      id: "all",
      label: t("rom.all-files"),
      icon: "mdi-folder-multiple-outline",
      count: files.value.length,
    },
  ];
  // Root always sits right after "All files" so the user's eye lands
  // on the most common entry point first; remaining folders follow
  // alphabetically by display label.
  const rootList = filesByFolder.value.get(ROOT);
  if (rootList && rootList.length > 0) {
    out.push({
      id: ROOT,
      label: t("rom.folder-root"),
      icon: folderIcon(ROOT),
      count: rootList.length,
    });
  }
  const folders = [...filesByFolder.value.keys()]
    .filter((f) => f !== ROOT)
    .sort((a, b) => folderLabel(a).localeCompare(folderLabel(b)));
  for (const folder of folders) {
    out.push({
      id: folder,
      label: folderLabel(folder),
      icon: folderIcon(folder),
      count: filesByFolder.value.get(folder)?.length ?? 0,
    });
  }
  return out;
});

const validSubtabIds = computed(
  () => new Set(subtabDefs.value.map((s) => s.id)),
);

// ---------- Subtab state (URL-persisted via `?subtab=`) ----------
function readSubtabFromRoute(): Subtab {
  const raw = route.query.subtab;
  if (typeof raw === "string" && validSubtabIds.value.has(raw as Subtab)) {
    return raw as Subtab;
  }
  return "all";
}

const subTab = ref<Subtab>(readSubtabFromRoute());

// If the currently-selected subtab no longer has files (e.g. after a
// rom refresh dropped that category), snap back to "all" so the user
// isn't staring at an empty pane.
watch(
  validSubtabIds,
  (ids) => {
    if (!ids.has(subTab.value)) subTab.value = "all";
  },
  { flush: "post" },
);

watch(subTab, (value) => {
  if (route.query.subtab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, subtab: value },
    });
  }
});

watch(
  () => route.query.subtab,
  (value) => {
    if (
      typeof value === "string" &&
      validSubtabIds.value.has(value as Subtab) &&
      value !== subTab.value
    ) {
      subTab.value = value as Subtab;
    }
  },
);

// When the user navigates away from the Files tab, drop the subtab
// param so it doesn't leak onto sibling tabs (mirrors MediaTab).
watch(
  () => route.query.tab,
  (value) => {
    if (value !== "files" && route.query.subtab) {
      const rest = { ...route.query };
      delete rest.subtab;
      router.replace({ path: route.path, query: rest });
    }
  },
);

// ---------- Filtered file list (driven by the active subtab) ----------
// "All files": Root first, then each present folder in alphabetical
// order (by label). Inside every bucket, files keep the path-based
// order from `files`. Folder-specific subtabs inherit that order
// directly from `filesByFolder`.
const filteredFiles = computed<RomFileSchema[]>(() => {
  if (subTab.value !== "all") {
    return filesByFolder.value.get(subTab.value as string) ?? [];
  }
  const out: RomFileSchema[] = [];
  const rootList = filesByFolder.value.get(ROOT);
  if (rootList) out.push(...rootList);
  const folders = [...filesByFolder.value.keys()]
    .filter((f) => f !== ROOT)
    .sort((a, b) => folderLabel(a).localeCompare(folderLabel(b)));
  for (const folder of folders) {
    out.push(...(filesByFolder.value.get(folder) ?? []));
  }
  return out;
});

// ---------- Selection ----------
const selectedIds = ref<Set<number>>(new Set());

// Reset selection whenever the active subtab or the rom changes —
// keeping selections across categories would let the user "Download
// selected" with files invisible to them, which is surprising.
watch([subTab, () => props.rom.id], () => {
  selectedIds.value = new Set();
});

const selectedCount = computed(() => {
  // Only count selections that are still in the filtered view —
  // protects against stale ids if the underlying rom file list
  // changes mid-selection (uploads, deletions in other tabs).
  let n = 0;
  for (const f of filteredFiles.value) if (selectedIds.value.has(f.id)) n++;
  return n;
});

const filteredCount = computed(() => filteredFiles.value.length);

const visibleAllSelected = computed(
  () => filteredCount.value > 0 && selectedCount.value === filteredCount.value,
);

const visibleSomeSelected = computed(
  () => selectedCount.value > 0 && !visibleAllSelected.value,
);

function isSelected(file: RomFileSchema): boolean {
  return selectedIds.value.has(file.id);
}

function toggleFile(file: RomFileSchema) {
  const next = new Set(selectedIds.value);
  if (next.has(file.id)) next.delete(file.id);
  else next.add(file.id);
  selectedIds.value = next;
}

function toggleVisible() {
  const next = new Set(selectedIds.value);
  if (visibleAllSelected.value) {
    for (const f of filteredFiles.value) next.delete(f.id);
  } else {
    for (const f of filteredFiles.value) next.add(f.id);
  }
  selectedIds.value = next;
}

function clearSelection() {
  selectedIds.value = new Set();
}

const selectedFiles = computed<RomFileSchema[]>(() =>
  filteredFiles.value.filter((f) => selectedIds.value.has(f.id)),
);

// ---------- Clipboard helper ----------
// Used by the per-subtab + per-selection copy-link buttons; per-file
// hash copying lives in HashChip itself.
async function copyDownloadLink(url: string) {
  try {
    await navigator.clipboard.writeText(url);
    snackbar.success(t("rom.download-link-copied"), {
      icon: "mdi-check-bold",
    });
  } catch {
    snackbar.error(t("rom.download-link-copy-failed"), {
      icon: "mdi-close-circle",
    });
  }
}

// ---------- Actions ----------
async function downloadFile(file: RomFileSchema) {
  await romApi.downloadRom({ rom: props.rom, fileIDs: [file.id] });
}

async function downloadSelected() {
  if (selectedCount.value === 0) return;
  await romApi.downloadRom({
    rom: props.rom,
    fileIDs: selectedFiles.value.map((f) => f.id),
  });
}

async function copyFileLink(file: RomFileSchema) {
  await copyDownloadLink(
    getDownloadLink({ rom: props.rom, fileIDs: [file.id] }),
  );
}

async function copySelectedLink() {
  if (selectedCount.value === 0) return;
  await copyDownloadLink(
    getDownloadLink({
      rom: props.rom,
      fileIDs: selectedFiles.value.map((f) => f.id),
    }),
  );
}

// ---------- Delete ----------
async function deleteFiles(toDelete: RomFileSchema[]) {
  if (toDelete.length === 0) return;

  const ok = await confirm({
    title: t("rom.delete-files-confirm-title", toDelete.length, {
      named: { n: toDelete.length },
    }),
    body: t("rom.delete-files-confirm-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;

  const results = await Promise.allSettled(
    toDelete.map((file) =>
      romApi.deleteRomFile({ romId: props.rom.id, fileId: file.id }),
    ),
  );

  const succeeded = results.filter((r) => r.status === "fulfilled").length;
  const failed = results.length - succeeded;

  if (succeeded > 0) {
    snackbar.success(
      t("rom.files-deleted-n", succeeded, { named: { n: succeeded } }),
      { icon: "mdi-check-bold" },
    );
  }
  if (failed > 0) {
    const firstError = results.find((r) => r.status === "rejected") as
      PromiseRejectedResult | undefined;
    snackbar.error(
      t("rom.file-delete-failed", {
        error: firstError ? errorMessage(firstError.reason) : "",
      }),
      { icon: "mdi-close-circle" },
    );
  }

  await refreshRom();

  // Redirect to the gallery if no files remain after deletion.
  const platformSlug = route.params["platform"] as string | undefined;
  if (romsStore.currentRom && romsStore.currentRom.files?.length === 0) {
    if (platformSlug) {
      await router.push({
        name: "platform",
        params: { platform: platformSlug },
      });
    } else {
      await router.push({ name: "home" });
    }
  }
}

async function deleteSelectedFiles() {
  const toDelete = selectedFiles.value;
  if (toDelete.length === 0) return;
  clearSelection();
  await deleteFiles(toDelete);
}

// ---------- Upload ----------
// One hidden `<input>` serves every folder: the active subtab decides
// the destination, and the dialog covers "All files" or a new folder.
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const uploadDialogOpen = ref(false);
const uploadStore = storeUpload();
const alive = useIsAlive();

const uploadFolders = computed<UploadFolderOption[]>(() =>
  subtabDefs.value
    .filter((s) => s.id !== "all" && s.id !== ROOT)
    .map((s) => ({ value: s.id, label: s.label })),
);

// Destination implied by the active subtab: "" for the ROM root, null
// when there is none ("All files") and the dialog has to ask.
const activeUploadFolder = computed<string | null>(() => {
  if (subTab.value === "all") return null;
  if (subTab.value === ROOT) return "";
  return subTab.value;
});

function triggerUpload() {
  if (uploading.value) return;
  if (activeUploadFolder.value === null) uploadDialogOpen.value = true;
  else fileInput.value?.click();
}

function onFilePick(event: Event) {
  const input = event.target as HTMLInputElement;
  const picked = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (picked.length === 0) return;
  void uploadFiles(activeUploadFolder.value ?? "", picked);
}

function onDialogSubmit(payload: { folder: string; files: File[] }) {
  uploadDialogOpen.value = false;
  void uploadFiles(payload.folder, payload.files);
}

function uploadErrorMessage(name: string, reason: unknown): string {
  const status = axios.isAxiosError(reason)
    ? reason.response?.status
    : undefined;
  if (status === 409) return t("rom.upload-file-exists", { name });
  const error = errorMessage(reason);
  if (status === 400) return t("rom.upload-file-rejected", { name, error });
  return t("rom.upload-file-failed", { name, error });
}

async function uploadFiles(folder: string, picked: File[]) {
  if (uploading.value) return;
  if (props.rom.has_simple_single_file) {
    const ok = await confirm({
      title: t("rom.convert-to-folder-title"),
      body: t("rom.convert-to-folder-body"),
      tone: "warning",
    });
    if (!ok) return;
  }

  uploading.value = true;
  try {
    const results = await romApi.uploadRoms({
      platformId: props.rom.platform_id,
      romId: props.rom.id,
      folder,
      filesToUpload: picked,
    });
    const ok = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.length - ok;
    if (ok > 0) {
      snackbar.success(
        failed
          ? t("rom.files-uploaded-with-failed", ok, {
              named: { n: ok, failed },
            })
          : t("rom.files-uploaded-n", ok, { named: { n: ok } }),
        { icon: "mdi-check-bold" },
      );
    } else {
      snackbar.warning(t("rom.no-files-uploaded"), {
        icon: "mdi-close-circle",
      });
    }
    // allSettled keeps the input order, so the index maps back to the file.
    const firstFailed = results.findIndex((r) => r.status === "rejected");
    if (firstFailed >= 0) {
      const rejected = results[firstFailed] as PromiseRejectedResult;
      snackbar.error(
        uploadErrorMessage(picked[firstFailed].name, rejected.reason),
      );
    }
    if (failed === 0) uploadStore.reset();
    if (!alive.value || ok === 0) return;
    await refreshRom();
    const landed = folder.split("/")[0];
    if (alive.value && landed && validSubtabIds.value.has(landed)) {
      subTab.value = landed;
    }
  } finally {
    uploading.value = false;
  }
}

async function refreshRom() {
  await refetchRom(props.rom.id);
}
</script>

<template>
  <input
    ref="fileInput"
    type="file"
    multiple
    class="r-v2-files__file-input"
    :aria-label="t('common.upload')"
    @change="onFilePick"
  />
  <UploadFilesDialog
    v-model="uploadDialogOpen"
    :folders="uploadFolders"
    :initial-folder="activeUploadFolder ?? ''"
    @submit="onDialogSubmit"
  />

  <div class="r-v2-files">
    <aside class="r-v2-files__sidebar">
      <ul
        class="r-v2-files__subtabs"
        role="tablist"
        aria-orientation="vertical"
      >
        <li v-for="tab in subtabDefs" :key="tab.id" class="r-v2-files__subtab">
          <button
            type="button"
            role="tab"
            class="r-v2-files__subtab-btn"
            :class="{
              'r-v2-files__subtab-btn--active': subTab === tab.id,
            }"
            :aria-selected="subTab === tab.id"
            @click="subTab = tab.id"
          >
            <RIcon :icon="tab.icon" size="16" />
            <span class="r-v2-files__subtab-label">{{ tab.label }}</span>
            <span v-if="tab.count > 0" class="r-v2-files__subtab-badge">
              {{ tab.count }}
            </span>
          </button>
        </li>
      </ul>
    </aside>

    <div class="r-v2-files__content">
      <!-- Section header — the sidebar's subtab label already names the
           section, so the header skips a redundant title and just hosts
           the Upload button on the right. Download-all / Copy-link are
           covered by the selection toolbar below (select-all then act). -->
      <header
        v-if="filteredFiles.length > 0 && canUpload"
        class="r-v2-files__section-head"
      >
        <div class="r-v2-files__section-actions">
          <RBtn
            variant="outlined"
            size="small"
            prepend-icon="mdi-cloud-upload-outline"
            :disabled="uploading"
            :loading="uploading"
            @click="triggerUpload"
          >
            {{ t("common.upload") }}
          </RBtn>
          <RTooltip :text="t('rom.upload-to-folder')" location="bottom">
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                icon="mdi-folder-upload-outline"
                variant="text"
                size="small"
                :aria-label="t('rom.upload-to-folder')"
                :disabled="uploading"
                @click="uploadDialogOpen = true"
              />
            </template>
          </RTooltip>
        </div>
      </header>

      <FilesSummary :rom="rom" />

      <!-- Selection toolbar — pinned above the list. Always visible
           so the select-all checkbox stays predictable; the per-
           selection action buttons fade in only when something is
           checked. -->
      <div v-if="filteredFiles.length > 0" class="r-v2-files__toolbar">
        <div class="r-v2-files__toolbar-select">
          <RCheckbox
            :model-value="visibleAllSelected"
            :indeterminate="visibleSomeSelected"
            size="sm"
            hide-details
            @update:model-value="toggleVisible"
          />
          <span class="r-v2-files__toolbar-status">
            <template v-if="selectedCount > 0">
              {{
                t("rom.files-selected-of", {
                  selected: selectedCount,
                  total: filteredCount,
                })
              }}
            </template>
            <template v-else>
              {{
                t("rom.files-count-n", filteredCount, {
                  named: { n: filteredCount },
                })
              }}
            </template>
          </span>
        </div>

        <div v-if="selectedCount > 0" class="r-v2-files__toolbar-actions">
          <RBtn
            icon="mdi-cloud-download-outline"
            variant="text"
            size="small"
            :tooltip="t('rom.download-selected')"
            :aria-label="t('rom.download-selected')"
            @click="downloadSelected"
          />
          <RBtn
            icon="mdi-link-variant"
            variant="text"
            size="small"
            :tooltip="t('rom.copy-link-action')"
            :aria-label="t('rom.copy-link-action')"
            @click="copySelectedLink"
          />
          <RBtn
            v-if="canDelete"
            icon="mdi-delete-outline"
            variant="text"
            color="danger"
            size="small"
            :tooltip="t('common.delete')"
            :aria-label="t('common.delete')"
            @click="deleteSelectedFiles"
          />
          <RBtn
            icon="mdi-close"
            variant="text"
            size="small"
            :tooltip="t('common.clear')"
            :aria-label="t('common.clear')"
            @click="clearSelection"
          />
        </div>
      </div>

      <!-- File list / empty state. -->
      <REmptyState
        v-if="filteredFiles.length === 0"
        icon="mdi-folder-off-outline"
        :title="t('rom.no-files-in-category')"
        :hint="t('rom.no-files-in-category-hint')"
      />

      <ul v-else class="r-v2-files__list">
        <FileRow
          v-for="(file, i) in filteredFiles"
          :key="file.id"
          class="r-v2-asset-fade"
          :style="{ '--asset-fade-i': i }"
          :file="file"
          :display-path="displayPath(file)"
          :relative-path="relativePath(file)"
          :selected="isSelected(file)"
          :show-row-icon="subTab === 'all'"
          :show-category-badge="subTab === 'all'"
          :can-delete="canDelete"
          @toggle="toggleFile(file)"
          @download="downloadFile(file)"
          @copy-link="copyFileLink(file)"
          @delete="deleteFiles([file])"
        />
      </ul>
    </div>
  </div>
</template>

<style scoped>
.r-v2-files {
  display: flex;
  align-items: stretch;
  gap: 24px;
  /* Anchor the FilesTab to `.r-v2-det__panel`'s visible viewport
     via absolute positioning rather than `height: 100%`. The panel
     has `overflow-y: auto`, which is a scroll container — percentage
     heights against such a parent flake (resolve to min-content when
     the descendant grid's intrinsic height grows under many files),
     and the file list ends up pushing the panel's outer scrollbar.
     Absolute + `inset: 0` pins us exactly to the visible viewport,
     and the grid below clips its overflow internally. */
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.r-v2-files__sidebar {
  width: 220px;
  flex-shrink: 0;
  /* Independent scroll context for the subtab list — without
     `min-height: 0` + an `overflow-y: auto` child, ROMs with many
     subfolders push tabs past the panel's visible area and they
     become unreachable. */
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* Subtab list — visually identical to MediaTab/SaveDataTab so the
   three tabs share a single navigation vocabulary. Scrolls internally
   when the folder count exceeds the available vertical space. */
.r-v2-files__subtabs {
  list-style: none;
  margin: 0;
  padding: 0 4px 4px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-v2-files__subtabs::-webkit-scrollbar {
  width: 4px;
}
.r-v2-files__subtabs::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
}
.r-v2-files__subtab {
  display: flex;
  flex-direction: column;
}
.r-v2-files__subtab-btn {
  width: 100%;
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-files__subtab-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-files__subtab-btn--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-files__subtab-label {
  flex: 1;
}
.r-v2-files__subtab-badge {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, currentColor 18%, transparent);
}

/* The hidden file input sits at the template root so the visible button
   can `.click()` it; display:none works fine since it never needs to be
   tabbable directly. */
.r-v2-files__file-input {
  display: none;
}

/* Section header — toolbar row at the top of the content column,
   mirroring ScreenshotsSubtab / MediaTab. The sidebar's subtab label
   names the section, so the header has no title — only the action
   cluster pushed to the right. */
.r-v2-files__section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.r-v2-files__section-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.r-v2-files__content {
  flex: 1;
  min-width: 0;
  /* Grid (auto / auto / auto / 1fr) instead of flex column: the `1fr`
     row forces the list to clip + scroll internally even with many
     files. Flex `min-height: 0` + `overflow-y: auto` on the list was
     unreliable here — the list's intrinsic min-content kept leaking
     through and pushed `.r-v2-det__panel` into showing its outer
     scrollbar. Rows: section header, summary, selection toolbar, list. */
  display: grid;
  grid-template-rows: auto auto auto 1fr;
  gap: var(--r-space-3);
  min-height: 0;
  overflow: hidden;
}

/* (Summary card + hash chip styles moved to FilesSummary / HashChip
   components.) */

/* Selection toolbar. */
.r-v2-files__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 4px;
  flex-shrink: 0;
  /* Reserve the height of the action cluster (small RBtn = 32px +
     6px×2 vertical padding) so toggling the selection state doesn't
     cause the toolbar to jump in height when the action buttons
     fade in. */
  min-height: 44px;
}
.r-v2-files__toolbar-select {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  cursor: pointer;
  user-select: none;
}
.r-v2-files__toolbar-status {
  font-weight: var(--r-font-weight-medium);
}
.r-v2-files__toolbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* File rows — sole scrollable area. Sits in the grid's `1fr` track,
   so the track width determines its size; `min-height: 0` lets the
   grid track shrink under min-content and `overflow-y: auto` keeps
   the rows scrolling inside. No `flex: 1` — grid items don't honour
   flex shorthand and it muddies the contract. */
.r-v2-files__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0 4px 4px 0;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-v2-files__list::-webkit-scrollbar {
  width: 4px;
}
.r-v2-files__list::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
}

/* Mobile: the details view scrolls as one document (no fixed inner panel),
   so FilesTab can't pin itself to a scroll viewport (`absolute; inset: 0`
   would collapse to zero height). Unwind it: stack the folder sidebar above
   the file list and drop every internal scroll so it flows with the page. */
html[data-bp~="sm-and-down"] .r-v2-files {
  position: static;
  inset: auto;
  overflow: visible;
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="sm-and-down"] .r-v2-files__sidebar {
  width: auto;
}
html[data-bp~="sm-and-down"] .r-v2-files__subtabs {
  flex: none;
  min-height: 0;
  overflow-y: visible;
}
html[data-bp~="sm-and-down"] .r-v2-files__content {
  display: flex;
  flex-direction: column;
  overflow: visible;
}
html[data-bp~="sm-and-down"] .r-v2-files__list {
  min-height: 0;
  overflow-y: visible;
}

/* (File-row styles moved to the FileRow component.) */

html[data-bp~="xs"] .r-v2-files {
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="xs"] .r-v2-files__sidebar {
  width: auto;
}
html[data-bp~="xs"] .r-v2-files__toolbar {
  flex-wrap: wrap;
}
</style>
