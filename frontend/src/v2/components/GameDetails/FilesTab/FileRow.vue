<script setup lang="ts">
// FileRow — a single file entry inside the FilesTab list.
//
// Owns the row layout: leading selection checkbox, filename block
// (icon + path), meta line (category chip + size + audio metadata),
// hash chip cluster, and the trailing Download / Copy-link actions.
// Selection / download / copy actions emit upward; the parent (the
// FilesTab orchestrator) keeps the selection set + dispatches the
// API calls.
//
// The parent also decides whether to render the category-icon at the
// row's leading edge and the category chip in the meta line — both
// are redundant inside folder subtabs where every row shares the same
// category, so we toggle them off there.
import { RBtn, RCheckbox, RChip, RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RomFileCategory, RomFileSchema } from "@/__generated__";
import { formatBytes } from "@/utils";
import HashChip from "@/v2/components/shared/HashChip.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = defineProps<{
  file: RomFileSchema;
  /** Filename rendered in the row; the parent strips the folder
   *  prefix inside folder subtabs and passes the result here. */
  displayPath: string;
  /** Full relative path — used for native title / aria-label so the
   *  context isn't lost when the displayed name is short. */
  relativePath: string;
  selected: boolean;
  /** Show the leading category icon (only useful in "All files"). */
  showRowIcon: boolean;
  /** Show the trailing category chip (only useful in "All files"). */
  showCategoryBadge: boolean;
}>();

const emit = defineEmits<{
  (e: "toggle"): void;
  (e: "download"): void;
  (e: "copyLink"): void;
}>();

// Shared category metadata — kept inline (instead of importing from
// FilesTab) so this row is self-contained. The chip / icon are only
// rendered when the parent says so, so the lookup stays cheap.
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
  screenshot: {
    label: t("rom.screenshots"),
    icon: "mdi-image-multiple-outline",
  },
}));

const categoryMeta = computed(() => {
  if (!props.file.category) return null;
  return CATEGORY_META.value[props.file.category as RomFileCategory] ?? null;
});

function formatDuration(seconds: number | null | undefined): string | null {
  if (!seconds || seconds <= 0) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

const audioDuration = computed(() =>
  formatDuration(props.file.track_meta?.duration_seconds),
);

const hasAnyHash = computed(
  () =>
    Boolean(props.file.sha1_hash) ||
    Boolean(props.file.chd_sha1_hash) ||
    Boolean(props.file.md5_hash) ||
    Boolean(props.file.crc_hash) ||
    Boolean(props.file.ra_hash),
);
</script>

<template>
  <li
    class="r-v2-file-row"
    :class="{ 'r-v2-file-row--selected': selected }"
    v-bind="$attrs"
  >
    <!-- The wrapper matches the filename's first-line box height
         (font-size × line-height) so `align-items: center` inside it
         lands the checkbox box on the filename's vertical centre,
         regardless of how many secondary lines stack below. -->
    <span class="r-v2-file-row__check">
      <RCheckbox
        :model-value="selected"
        size="sm"
        hide-details
        bare
        :aria-label="t('rom.select-file', { path: relativePath })"
        @update:model-value="emit('toggle')"
      />
    </span>

    <div class="r-v2-file-row__main">
      <div class="r-v2-file-row__name">
        <RIcon
          v-if="showRowIcon"
          :icon="categoryMeta?.icon ?? 'mdi-file-outline'"
          size="14"
          class="r-v2-file-row__icon"
        />
        <span class="r-v2-file-row__path" :title="relativePath">
          {{ displayPath }}
        </span>
      </div>

      <div class="r-v2-file-row__meta">
        <RChip
          v-if="showCategoryBadge && file.category"
          :label="true"
          size="x-small"
          color="primary"
          variant="translucent"
        >
          {{ categoryMeta?.label ?? file.category }}
        </RChip>
        <span class="r-v2-file-row__size">
          {{ formatBytes(file.file_size_bytes) }}
        </span>
        <template v-if="audioDuration">
          <span class="r-v2-file-row__sep">·</span>
          <span class="r-v2-file-row__duration">{{ audioDuration }}</span>
        </template>
        <template v-if="file.track_meta?.title">
          <span class="r-v2-file-row__sep">·</span>
          <span class="r-v2-file-row__track-title">
            {{ file.track_meta.title }}
            <template v-if="file.track_meta.artist">
              — {{ file.track_meta.artist }}
            </template>
          </span>
        </template>
      </div>

      <div v-if="hasAnyHash" class="r-v2-file-row__hashes">
        <HashChip
          v-if="file.sha1_hash"
          label="SHA-1"
          :value="file.sha1_hash"
          compact
        />
        <HashChip
          v-if="file.chd_sha1_hash"
          label="CHD SHA-1"
          :value="file.chd_sha1_hash"
          compact
        />
        <HashChip
          v-if="file.md5_hash"
          label="MD5"
          :value="file.md5_hash"
          compact
        />
        <HashChip
          v-if="file.crc_hash"
          label="CRC"
          :value="file.crc_hash"
          compact
        />
        <HashChip
          v-if="file.ra_hash"
          label="RA"
          :value="file.ra_hash"
          compact
        />
      </div>
    </div>

    <div class="r-v2-file-row__actions">
      <RBtn
        icon="mdi-download-outline"
        variant="text"
        size="small"
        :tooltip="t('rom.download-file')"
        :aria-label="t('rom.download-named', { name: relativePath })"
        @click="emit('download')"
      />
      <RBtn
        icon="mdi-link-variant"
        variant="text"
        size="small"
        :tooltip="t('rom.copy-download-link-title')"
        :aria-label="t('rom.copy-link-for', { path: relativePath })"
        @click="emit('copyLink')"
      />
    </div>
  </li>
</template>

<style scoped>
.r-v2-file-row {
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
.r-v2-file-row:hover {
  border-color: var(--r-color-border-strong);
}
.r-v2-file-row--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 40%,
    transparent
  );
}

.r-v2-file-row__check {
  /* Mirror the filename's line box so the checkbox aligns with the
     filename's optical centre instead of the row's top edge. The
     filename uses `font-size: 13px` (see __row-path) — multiplying
     by the inherited body line-height (~1.5) yields ~19.5px, which
     we round to 20px here. `align-items: center` then drops the
     16px sm-checkbox box on the line centre. */
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  flex-shrink: 0;
}

.r-v2-file-row__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* Slightly larger gap between filename and the meta / hash lines so
     they read as secondary "details" rather than continuation of the
     filename. */
  gap: 6px;
}

.r-v2-file-row__name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  min-width: 0;
  /* Pin the line box to the same height the checkbox wrapper uses so
     `align-items: center` puts both on the same horizontal midline.
     Without an explicit `line-height`, the inherited 1.5 leaves
     ~3px of extra leading that visually drops the filename below
     the checkbox box. */
  line-height: 1;
  min-height: 20px;
}
.r-v2-file-row__icon {
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
.r-v2-file-row__path {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--r-font-mono, monospace);
  font-size: 12.5px;
}

.r-v2-file-row__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  /* Tuned down a notch from the filename's 13px so the chip + size
     line reads as supporting detail; `fg-faint` (vs `fg-muted`) dims
     it further without losing legibility. */
  font-size: 11px;
  color: var(--r-color-fg-faint);
}
.r-v2-file-row__size {
  font-variant-numeric: tabular-nums;
}
.r-v2-file-row__track-title {
  color: var(--r-color-fg);
}
.r-v2-file-row__sep {
  opacity: 0.5;
}

.r-v2-file-row__hashes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.r-v2-file-row__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  /* Row uses `align-items: flex-start` so the checkbox lines up with
     the filename top; the actions cluster overrides to centre against
     the row's full height (name + meta + hashes) so the buttons sit
     mid-row instead of clinging to the top. */
  align-self: center;
}
</style>
