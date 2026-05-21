<script setup lang="ts">
// FilesTab — browse + interact with the individual files that make up
// a (potentially multi-file) ROM.
//
// Layout mirrors MediaTab / SaveDataTab: a vertical subtab list on the
// left with an attached RCollapsible action panel under the active
// subtab, and a content column on the right.
//
// Sidebar surfaces a subtab per file category that's actually present
// in the ROM (plus an "All files" entry and an optional
// "Uncategorized" bucket). The inline panel under the active subtab
// hosts bulk actions for that subset — download every file in this
// category, copy the matching download link.
//
// Content column shows:
//   * a ROM-info card at the top (total size, revision, ROM-level
//     hashes — click any to copy)
//   * a selection toolbar (select-all + per-selection actions) once
//     the active subtab has files
//   * one row per file with checkbox, relative path, category badge,
//     size, per-file hashes (click to copy), and per-row Download +
//     Copy-link buttons.
//
// All destructive ops are out of scope here — file deletion lives in
// MediaTab (manuals, soundtracks) and the EditRom dialog. This tab
// is read-only browsing + downloads.
import {
  RBtn,
  RCheckbox,
  RChip,
  RCollapsible,
  REmptyState,
  RIcon,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type {
  DetailedRomSchema,
  RomFileCategory,
  RomFileSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import { formatBytes, getDownloadLink } from "@/utils";
import MissingFSBadge from "@/v2/components/shared/MissingFSBadge.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();

const snackbar = useSnackbar();
const route = useRoute();
const router = useRouter();

// ---------- Category metadata ----------
// Order here defines the order subtabs appear in the sidebar (and the
// order categories are listed when "All files" groups them). "game"
// first since it's the canonical bucket; everything else follows the
// rough "shipped with the cartridge" → "user / modder content" arc.
const CATEGORY_META: Record<RomFileCategory, { label: string; icon: string }> =
  {
    game: { label: "Game", icon: "mdi-gamepad-variant-outline" },
    dlc: { label: "DLC", icon: "mdi-puzzle-outline" },
    update: { label: "Update", icon: "mdi-update" },
    patch: { label: "Patch", icon: "mdi-bandage" },
    mod: { label: "Mod", icon: "mdi-tools" },
    hack: { label: "Hack", icon: "mdi-pencil-ruler" },
    translation: { label: "Translation", icon: "mdi-translate" },
    demo: { label: "Demo", icon: "mdi-flask-outline" },
    prototype: { label: "Prototype", icon: "mdi-test-tube" },
    cheat: { label: "Cheat", icon: "mdi-incognito" },
    manual: { label: "Manual", icon: "mdi-book-open-page-variant-outline" },
    soundtrack: { label: "Soundtrack", icon: "mdi-music-note-outline" },
  };

const UNCATEGORIZED = "uncategorized" as const;
type Subtab = "all" | RomFileCategory | typeof UNCATEGORIZED;

const CATEGORY_ORDER = Object.keys(CATEGORY_META) as RomFileCategory[];

// ---------- File grouping ----------
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

const filesByCategory = computed(() => {
  const map = new Map<Subtab, RomFileSchema[]>();
  for (const f of files.value) {
    const key: Subtab = (f.category as RomFileCategory | null) ?? UNCATEGORIZED;
    const bucket = map.get(key);
    if (bucket) bucket.push(f);
    else map.set(key, [f]);
  }
  return map;
});

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
      label: "All files",
      icon: "mdi-folder-multiple-outline",
      count: files.value.length,
    },
  ];
  for (const cat of CATEGORY_ORDER) {
    const list = filesByCategory.value.get(cat);
    if (list && list.length > 0) {
      out.push({
        id: cat,
        label: CATEGORY_META[cat].label,
        icon: CATEGORY_META[cat].icon,
        count: list.length,
      });
    }
  }
  const uncat = filesByCategory.value.get(UNCATEGORIZED);
  if (uncat && uncat.length > 0) {
    out.push({
      id: UNCATEGORIZED,
      label: "Uncategorized",
      icon: "mdi-help-circle-outline",
      count: uncat.length,
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
const filteredFiles = computed<RomFileSchema[]>(() => {
  if (subTab.value === "all") return files.value;
  return filesByCategory.value.get(subTab.value) ?? [];
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

// ---------- Hash / metadata helpers ----------
function shortHash(value: string | null): string | null {
  if (!value) return null;
  if (value.length <= 14) return value;
  return `${value.substring(0, 6)}…${value.substring(value.length - 6)}`;
}

async function copyToClipboard(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    snackbar.success(`${label} copied to clipboard.`, {
      icon: "mdi-check-bold",
    });
  } catch {
    snackbar.error(`Couldn't copy ${label.toLowerCase()}.`, {
      icon: "mdi-close-circle",
    });
  }
}

function formatDuration(seconds: number | null | undefined): string | null {
  if (!seconds || seconds <= 0) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ---------- ROM-level summary ----------
const romHashes = computed(() =>
  [
    { label: "SHA-1", value: props.rom.sha1_hash },
    { label: "MD5", value: props.rom.md5_hash },
    { label: "CRC", value: props.rom.crc_hash },
  ].filter((h) => h.value),
);

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
  const url = getDownloadLink({ rom: props.rom, fileIDs: ids });
  await copyToClipboard(url, "Download link");
}

async function copyFileLink(file: RomFileSchema) {
  const url = getDownloadLink({ rom: props.rom, fileIDs: [file.id] });
  await copyToClipboard(url, "Download link");
}

async function copySelectedLink() {
  if (selectedCount.value === 0) return;
  const url = getDownloadLink({
    rom: props.rom,
    fileIDs: selectedFiles.value.map((f) => f.id),
  });
  await copyToClipboard(url, "Download link");
}

// ---------- Display helpers ----------
function categoryMeta(file: RomFileSchema) {
  if (!file.category) return null;
  return CATEGORY_META[file.category as RomFileCategory] ?? null;
}
</script>

<template>
  <div class="r-v2-files">
    <aside class="r-v2-files__sidebar">
      <ul
        class="r-v2-files__subtabs"
        role="tablist"
        aria-orientation="vertical"
      >
        <li v-for="t in subtabDefs" :key="t.id" class="r-v2-files__subtab">
          <button
            type="button"
            role="tab"
            class="r-v2-files__subtab-btn"
            :class="{
              'r-v2-files__subtab-btn--active': subTab === t.id,
              'r-v2-files__subtab-btn--joined': subTab === t.id && t.count > 0,
            }"
            :aria-selected="subTab === t.id"
            @click="subTab = t.id"
          >
            <RIcon :icon="t.icon" size="16" />
            <span class="r-v2-files__subtab-label">{{ t.label }}</span>
            <span v-if="t.count > 0" class="r-v2-files__subtab-badge">
              {{ t.count }}
            </span>
          </button>

          <RCollapsible
            :model-value="subTab === t.id && t.count > 0"
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
                {{ t.id === "all" ? "Download all" : "Download" }}
              </RBtn>
              <RBtn
                variant="outlined"
                prepend-icon="mdi-link-variant"
                block
                @click="copySubtabLink"
              >
                Copy link
              </RBtn>
            </div>
          </RCollapsible>
        </li>
      </ul>
    </aside>

    <div class="r-v2-files__content">
      <!-- ROM-level summary card: name, size, hashes, missing-from-fs flag. -->
      <section class="r-v2-files__summary">
        <header class="r-v2-files__summary-head">
          <div class="r-v2-files__summary-title">
            <RIcon icon="mdi-folder-outline" size="18" />
            <span class="r-v2-files__summary-name">
              {{ rom.fs_name }}
            </span>
            <MissingFSBadge
              v-if="rom.missing_from_fs"
              :text="`Missing from filesystem: ${rom.fs_path}/${rom.fs_name}`"
            />
          </div>
          <div class="r-v2-files__summary-stats">
            <span
              >{{ files.length }} file{{ files.length === 1 ? "" : "s" }}</span
            >
            <span class="r-v2-files__sep">·</span>
            <span>{{ formatBytes(rom.fs_size_bytes) }}</span>
            <template v-if="rom.revision">
              <span class="r-v2-files__sep">·</span>
              <span>Rev. {{ rom.revision }}</span>
            </template>
          </div>
        </header>

        <div v-if="romHashes.length > 0" class="r-v2-files__summary-hashes">
          <button
            v-for="h in romHashes"
            :key="h.label"
            type="button"
            class="r-v2-files__hash"
            :title="`Click to copy ${h.label}`"
            @click="copyToClipboard(h.value as string, h.label)"
          >
            <span class="r-v2-files__hash-label">{{ h.label }}</span>
            <span class="r-v2-files__hash-value">
              {{ shortHash(h.value) }}
            </span>
            <RIcon icon="mdi-content-copy" size="12" />
          </button>
        </div>
      </section>

      <!-- Selection toolbar — pinned above the list. Always visible
           so the select-all checkbox stays predictable; the per-
           selection action buttons fade in only when something is
           checked. -->
      <div v-if="filteredFiles.length > 0" class="r-v2-files__toolbar">
        <label class="r-v2-files__toolbar-select">
          <RCheckbox
            :model-value="visibleAllSelected"
            :indeterminate="visibleSomeSelected"
            size="sm"
            hide-details
            @update:model-value="toggleVisible"
          />
          <span class="r-v2-files__toolbar-status">
            <template v-if="selectedCount > 0">
              {{ selectedCount }} of {{ filteredCount }} selected
            </template>
            <template v-else>
              {{ filteredCount }} file{{ filteredCount === 1 ? "" : "s" }}
            </template>
          </span>
        </label>

        <div v-if="selectedCount > 0" class="r-v2-files__toolbar-actions">
          <RBtn
            variant="outlined"
            prepend-icon="mdi-cloud-download-outline"
            size="small"
            @click="downloadSelected"
          >
            Download selected
          </RBtn>
          <RBtn
            variant="outlined"
            prepend-icon="mdi-link-variant"
            size="small"
            @click="copySelectedLink"
          >
            Copy link
          </RBtn>
          <RBtn
            variant="text"
            prepend-icon="mdi-close"
            size="small"
            @click="clearSelection"
          >
            Clear
          </RBtn>
        </div>
      </div>

      <!-- File list / empty state. -->
      <REmptyState
        v-if="filteredFiles.length === 0"
        icon="mdi-folder-off-outline"
        title="No files in this category"
        hint="Switch to another category from the sidebar to see this ROM's other files."
      />

      <ul v-else class="r-v2-files__list">
        <li
          v-for="file in filteredFiles"
          :key="file.id"
          class="r-v2-files__row"
          :class="{ 'r-v2-files__row--selected': isSelected(file) }"
        >
          <RCheckbox
            :model-value="isSelected(file)"
            size="sm"
            hide-details
            class="r-v2-files__row-check"
            :aria-label="`Select ${relativePath(file)}`"
            @update:model-value="toggleFile(file)"
          />

          <div class="r-v2-files__row-main">
            <div class="r-v2-files__row-name">
              <RIcon
                :icon="categoryMeta(file)?.icon ?? 'mdi-file-outline'"
                size="14"
                class="r-v2-files__row-icon"
              />
              <span class="r-v2-files__row-path">{{ relativePath(file) }}</span>
            </div>

            <div class="r-v2-files__row-meta">
              <RChip
                v-if="file.category"
                :label="true"
                size="x-small"
                color="primary"
                variant="translucent"
              >
                {{ categoryMeta(file)?.label ?? file.category }}
              </RChip>
              <span class="r-v2-files__row-size">
                {{ formatBytes(file.file_size_bytes) }}
              </span>
              <template
                v-if="
                  file.audio_meta &&
                  formatDuration(file.audio_meta.duration_seconds)
                "
              >
                <span class="r-v2-files__sep">·</span>
                <span class="r-v2-files__row-duration">
                  {{ formatDuration(file.audio_meta.duration_seconds) }}
                </span>
              </template>
              <template v-if="file.audio_meta?.title">
                <span class="r-v2-files__sep">·</span>
                <span class="r-v2-files__row-track-title">
                  {{ file.audio_meta.title }}
                  <template v-if="file.audio_meta.artist">
                    — {{ file.audio_meta.artist }}
                  </template>
                </span>
              </template>
            </div>

            <div
              v-if="file.sha1_hash || file.md5_hash || file.crc_hash"
              class="r-v2-files__row-hashes"
            >
              <button
                v-if="file.sha1_hash"
                type="button"
                class="r-v2-files__hash r-v2-files__hash--compact"
                :title="`SHA-1: ${file.sha1_hash} (click to copy)`"
                @click="copyToClipboard(file.sha1_hash, 'SHA-1')"
              >
                <span class="r-v2-files__hash-label">SHA-1</span>
                <span class="r-v2-files__hash-value">
                  {{ shortHash(file.sha1_hash) }}
                </span>
              </button>
              <button
                v-if="file.md5_hash"
                type="button"
                class="r-v2-files__hash r-v2-files__hash--compact"
                :title="`MD5: ${file.md5_hash} (click to copy)`"
                @click="copyToClipboard(file.md5_hash, 'MD5')"
              >
                <span class="r-v2-files__hash-label">MD5</span>
                <span class="r-v2-files__hash-value">
                  {{ shortHash(file.md5_hash) }}
                </span>
              </button>
              <button
                v-if="file.crc_hash"
                type="button"
                class="r-v2-files__hash r-v2-files__hash--compact"
                :title="`CRC: ${file.crc_hash} (click to copy)`"
                @click="copyToClipboard(file.crc_hash, 'CRC')"
              >
                <span class="r-v2-files__hash-label">CRC</span>
                <span class="r-v2-files__hash-value">
                  {{ file.crc_hash }}
                </span>
              </button>
            </div>
          </div>

          <div class="r-v2-files__row-actions">
            <RBtn
              icon="mdi-download-outline"
              variant="text"
              size="small"
              tooltip="Download file"
              :aria-label="`Download ${relativePath(file)}`"
              @click="downloadFile(file)"
            />
            <RBtn
              icon="mdi-link-variant"
              variant="text"
              size="small"
              tooltip="Copy download link"
              :aria-label="`Copy download link for ${relativePath(file)}`"
              @click="copyFileLink(file)"
            />
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.r-v2-files {
  display: flex;
  align-items: stretch;
  gap: 24px;
  height: 100%;
  min-height: 0;
}

.r-v2-files__sidebar {
  width: 220px;
  flex-shrink: 0;
}

/* Subtab list — visually identical to MediaTab/SaveDataTab so the
   three tabs share a single navigation vocabulary. */
.r-v2-files__subtabs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.r-v2-files__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: var(--r-space-3);
  overflow: hidden;
}

/* ROM-level summary card. */
.r-v2-files__summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  flex-shrink: 0;
}
.r-v2-files__summary-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-files__summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg);
  font-size: 13.5px;
  font-weight: var(--r-font-weight-medium);
  min-width: 0;
}
.r-v2-files__summary-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-files__summary-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  flex-wrap: wrap;
}
.r-v2-files__summary-hashes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

/* Hash chip — a button-styled chip so click-to-copy reads as
   interactive without overloading RChip with click handlers. */
.r-v2-files__hash {
  appearance: none;
  background: var(--r-color-bg);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: var(--r-radius-sm);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-files__hash:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
  border-color: var(--r-color-border-strong);
}
.r-v2-files__hash-label {
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.02em;
  color: var(--r-color-fg-muted);
}
.r-v2-files__hash-value {
  font-family: var(--r-font-mono, monospace);
  color: var(--r-color-fg);
}
.r-v2-files__hash--compact {
  padding: 2px 6px;
  font-size: 10.5px;
  border-radius: 4px;
}

/* Selection toolbar. */
.r-v2-files__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 4px;
  flex-shrink: 0;
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

/* File rows — sole scrollable area. */
.r-v2-files__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0 4px 4px 0;
  flex: 1;
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

.r-v2-files__row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-files__row:hover {
  border-color: var(--r-color-border-strong);
}
.r-v2-files__row--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 40%,
    transparent
  );
}

.r-v2-files__row-check {
  margin-top: 1px;
  flex-shrink: 0;
}

.r-v2-files__row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-files__row-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  min-width: 0;
}
.r-v2-files__row-icon {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
.r-v2-files__row-path {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--r-font-mono, monospace);
  font-size: 12.5px;
}

.r-v2-files__row-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
}
.r-v2-files__row-size {
  font-variant-numeric: tabular-nums;
}
.r-v2-files__row-track-title {
  color: var(--r-color-fg);
}
.r-v2-files__sep {
  opacity: 0.5;
}

.r-v2-files__row-hashes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.r-v2-files__row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

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
