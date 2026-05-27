<script setup lang="ts">
// FilesTab — browse + interact with the individual files that make up
// a (potentially multi-file) ROM.
//
// Layout mirrors MediaTab / SaveDataTab: a vertical subtab list on the
// left with an attached RCollapsible action panel under the active
// subtab, and a content column on the right.
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
// Sidebar action panel (per active subtab):
//   * Download all / Copy link — always wired for any subtab.
//   * Upload — only wired for the "manual" and "soundtrack" folders
//     (the only places the backend supports adding files to an
//     existing ROM today). Other subtabs render a disabled Upload
//     button with a "coming soon" tooltip so the affordance is
//     visible but truthful about its current reach.
//
// Content column:
//   * ROM-info card (size, revision, ROM-level hashes — click to copy)
//   * Selection toolbar (select-all + per-selection actions)
//   * One row per file with checkbox, relative path, category chip,
//     size, per-file hashes (click to copy), and per-row Download +
//     Copy-link buttons.
//
// All destructive ops live elsewhere (MediaTab handles manual /
// soundtrack deletion, EditRom dialog handles whole-ROM deletion).
// This tab is browse + download + (limited) upload only.
import {
  RBtn,
  RCheckbox,
  RCollapsible,
  REmptyState,
  RIcon,
  RTooltip,
} from "@v2/lib";
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
import { getDownloadLink } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import FileRow from "./FileRow.vue";
import FilesSummary from "./FilesSummary.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();

const { t } = useI18n();
const snackbar = useSnackbar();
const route = useRoute();
const router = useRouter();
const romsStore = storeRoms();

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
  soundtrack: {
    label: t("rom.soundtrack"),
    icon: "mdi-music-note-outline",
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

function relativePath(file: RomFileSchema): string {
  return (
    file.full_path.replace(props.rom.full_path, "").replace(/^\//, "") ||
    file.file_name
  );
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

// Backend `RomFileCategory` derived from a folder name — used to
// pick the right upload endpoint. Plurals collapse to their singular
// (`cheats/` → `cheat`).
function folderToCategory(folder: string): RomFileCategory | null {
  const lower = folder.toLowerCase();
  const meta = FOLDER_META.value[lower];
  if (!meta) return null;
  // Look up the matching enum value by reverse-mapping the label.
  for (const key of Object.keys(CATEGORY_META.value) as RomFileCategory[]) {
    if (CATEGORY_META.value[key] === meta) return key;
  }
  return null;
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

// Backend-supported upload destinations. Other subtabs render the
// upload button disabled with a "coming soon" tooltip — see X.B in
// the v2 constitution for the pending backend endpoint.
function uploadSupportsSubtab(id: Subtab): "manual" | "soundtrack" | null {
  if (id === "all" || id === ROOT) return null;
  const cat = folderToCategory(id as string);
  if (cat === "manual") return "manual";
  if (cat === "soundtrack") return "soundtrack";
  return null;
}

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

async function downloadSubtab() {
  // "all" → download whole ROM (empty fileIDs == full content)
  const ids =
    subTab.value === "all" ? [] : filteredFiles.value.map((f) => f.id);
  await romApi.downloadRom({ rom: props.rom, fileIDs: ids });
}

async function downloadSelected() {
  if (selectedCount.value === 0) return;
  await romApi.downloadRom({
    rom: props.rom,
    fileIDs: selectedFiles.value.map((f) => f.id),
  });
}

async function copySubtabLink() {
  const ids =
    subTab.value === "all" ? [] : filteredFiles.value.map((f) => f.id);
  await copyDownloadLink(getDownloadLink({ rom: props.rom, fileIDs: ids }));
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

// ---------- Upload ----------
// One hidden `<input>` per supported target so each subtab's upload
// button can route through the matching backend endpoint without a
// dialog. Folder-based ROMs only — `uploadManualFiles` and
// `uploadSoundtracks` both 400 on single-file ROMs.
const manualUploadInput = ref<HTMLInputElement | null>(null);
const soundtrackUploadInput = ref<HTMLInputElement | null>(null);
const uploadingManual = ref(false);
const uploadingSoundtrack = ref(false);

const uploadDisabledReason = computed<string | null>(() => {
  if (props.rom.has_simple_single_file) {
    return t("rom.upload-needs-folder");
  }
  return null;
});

function triggerUpload() {
  const target = uploadSupportsSubtab(subTab.value);
  if (!target) return;
  if (uploadDisabledReason.value) return;
  if (target === "manual") manualUploadInput.value?.click();
  else soundtrackUploadInput.value?.click();
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

async function onManualUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const fileList = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (fileList.length === 0 || uploadingManual.value) return;

  uploadingManual.value = true;
  try {
    const responses = await romApi.uploadManualFiles({
      romId: props.rom.id,
      filesToUpload: fileList,
    });
    const successful = responses.filter((r) => r.status === "fulfilled").length;
    const failed = responses.length - successful;
    if (successful > 0) {
      snackbar.success(
        failed
          ? t("rom.manual-files-uploaded-with-failed", {
              n: successful,
              failed,
            })
          : t("rom.manual-files-uploaded-n", successful, {
              named: { n: successful },
            }),
        { icon: "mdi-check-bold" },
      );
      await refreshRom();
    } else {
      snackbar.warning(t("rom.no-files-uploaded"), {
        icon: "mdi-close-circle",
      });
    }
  } finally {
    uploadingManual.value = false;
  }
}

async function onSoundtrackUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const fileList = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (fileList.length === 0 || uploadingSoundtrack.value) return;

  uploadingSoundtrack.value = true;
  try {
    const responses = await romApi.uploadSoundtracks({
      romId: props.rom.id,
      filesToUpload: fileList,
    });
    const successful = responses.filter((r) => r.status === "fulfilled").length;
    const failed = responses.length - successful;
    if (successful > 0) {
      snackbar.success(
        failed
          ? t("rom.tracks-uploaded-with-failed", { n: successful, failed })
          : t("rom.tracks-uploaded-n", successful, {
              named: { n: successful },
            }),
        { icon: "mdi-check-bold" },
      );
      await refreshRom();
    } else {
      snackbar.warning(t("rom.no-tracks-uploaded"), {
        icon: "mdi-close-circle",
      });
    }
  } finally {
    uploadingSoundtrack.value = false;
  }
}

// Per-subtab upload affordance computed for the inline action panel.
interface SubtabUploadState {
  /** Whether the button should be clickable. */
  enabled: boolean;
  /** Tooltip surfaced when disabled, null otherwise. */
  reason: string | null;
  /** Show a spinner while an upload is in flight. */
  loading: boolean;
}

function uploadStateForSubtab(id: Subtab): SubtabUploadState {
  const target = uploadSupportsSubtab(id);
  if (!target) {
    return {
      enabled: false,
      reason: t("rom.upload-not-supported-here"),
      loading: false,
    };
  }
  if (uploadDisabledReason.value) {
    return {
      enabled: false,
      reason: uploadDisabledReason.value,
      loading: false,
    };
  }
  return {
    enabled: true,
    reason: null,
    loading:
      target === "manual" ? uploadingManual.value : uploadingSoundtrack.value,
  };
}
</script>

<template>
  <!-- Hidden file inputs drive the per-subtab upload buttons. Only the
       Manual / Soundtrack subtabs have a working backend pathway right
       now — see `uploadSupportsSubtab` in the script. -->
  <input
    ref="manualUploadInput"
    type="file"
    accept="application/pdf"
    multiple
    class="r-v2-files__file-input"
    :aria-label="t('rom.upload-manual-files')"
    @change="onManualUpload"
  />
  <input
    ref="soundtrackUploadInput"
    type="file"
    accept="audio/*,.flac,.opus"
    multiple
    class="r-v2-files__file-input"
    :aria-label="t('rom.upload-soundtrack-files')"
    @change="onSoundtrackUpload"
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
              'r-v2-files__subtab-btn--joined':
                subTab === tab.id && tab.count > 0,
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

          <RCollapsible
            :model-value="subTab === tab.id && tab.count > 0"
            attached
            class="r-v2-files__subtab-panel"
          >
            <div class="r-v2-files__subtab-panel-inner">
              <RBtn
                variant="outlined"
                prepend-icon="mdi-cloud-download-outline"
                block
                @click="downloadSubtab"
              >
                {{ t("rom.download-all") }}
              </RBtn>
              <RBtn
                variant="outlined"
                prepend-icon="mdi-link-variant"
                block
                @click="copySubtabLink"
              >
                {{ t("rom.copy-link-action") }}
              </RBtn>

              <!-- Upload — wired only for Manual / Soundtrack folders;
                   other subtabs render disabled with a tooltip
                   explaining the pending backend work. -->
              <div class="r-v2-files__upload-slot">
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  :disabled="!uploadStateForSubtab(tab.id).enabled"
                  :loading="uploadStateForSubtab(tab.id).loading"
                  @click="triggerUpload"
                >
                  {{ t("common.upload") }}
                </RBtn>
                <RTooltip
                  v-if="uploadStateForSubtab(tab.id).reason"
                  :text="uploadStateForSubtab(tab.id).reason ?? ''"
                  location="bottom"
                  activator="parent"
                />
              </div>
            </div>
          </RCollapsible>
        </li>
      </ul>
    </aside>

    <div class="r-v2-files__content">
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
            variant="outlined"
            prepend-icon="mdi-cloud-download-outline"
            size="small"
            @click="downloadSelected"
          >
            {{ t("rom.download-selected") }}
          </RBtn>
          <RBtn
            variant="outlined"
            prepend-icon="mdi-link-variant"
            size="small"
            @click="copySelectedLink"
          >
            {{ t("rom.copy-link-action") }}
          </RBtn>
          <RBtn
            variant="text"
            prepend-icon="mdi-close"
            size="small"
            @click="clearSelection"
          >
            {{ t("common.clear") }}
          </RBtn>
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
          v-for="file in filteredFiles"
          :key="file.id"
          :file="file"
          :display-path="displayPath(file)"
          :relative-path="relativePath(file)"
          :selected="isSelected(file)"
          :show-row-icon="subTab === 'all'"
          :show-category-badge="subTab === 'all'"
          @toggle="toggleFile(file)"
          @download="downloadFile(file)"
          @copy-link="copyFileLink(file)"
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
.r-v2-files__subtab-btn--joined {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
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

.r-v2-files__subtab-panel {
  margin-bottom: var(--r-space-1);
}
.r-v2-files__subtab-panel-inner {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  padding: var(--r-space-3);
}

/* Hidden file inputs sit at the template root so the visible buttons
   can `.click()` them — display:none works fine since we never need
   them to be tabbable directly. */
.r-v2-files__file-input {
  display: none;
}

/* Wrapper around the Upload button so RTooltip can attach to a
   non-disabled positioned ancestor; pointer-events on the disabled
   button itself swallow the tooltip's hover detection. */
.r-v2-files__upload-slot {
  position: relative;
}

.r-v2-files__content {
  flex: 1;
  min-width: 0;
  /* Grid (auto / auto / 1fr) instead of flex column: the `1fr` row
     forces the list to clip + scroll internally even with many files.
     Flex `min-height: 0` + `overflow-y: auto` on the list was unreliable
     here — the list's intrinsic min-content kept leaking through and
     pushed `.r-v2-det__panel` into showing its outer scrollbar. */
  display: grid;
  grid-template-rows: auto auto 1fr;
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
