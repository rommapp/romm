<script setup lang="ts">
// LogViewer — real-time backend log viewer, the Logs page's second tab.
//
// On open it backfills the last N buffered lines from `GET /logs`, then
// streams new lines live over Socket.IO (`logs:entry`, emitted to the
// `admin` room by the backend forwarder). State is view-scoped and
// ephemeral (constitution §VI.D): a capped in-memory ring buffer, no
// store, no global lifecycle — backfill covers re-open.
//
// The list is windowed with RVirtualScroller, which also scrolls the toolbar
// above it. Rows are single-line monospace (terminal style) and cut long
// lines short; the full message is surfaced on hover via RTooltip and copied
// on click. The newest line is on top: while the top is in view new lines show
// up there, otherwise the view holds still and "jump to latest" goes back up.
import { RBtn, RSelect, RTextField, RTooltip, RVirtualScroller } from "@v2/lib";
import { computed, nextTick, onBeforeMount, ref } from "vue";
import { useI18n } from "vue-i18n";
import api from "@/services/api";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

const { t } = useI18n();
const snackbar = useSnackbar();

interface LogEntry {
  ts: number;
  level: string;
  module: string;
  message: string;
}

interface LogRow extends LogEntry {
  // Client-side monotonic key — the backend payload has no id, and a
  // stable key keeps virtual-scroller rows from re-patching on front
  // eviction.
  seq: number;
  // The message as emitted, before newline folding. What the tooltip,
  // the clipboard and the downloaded file use.
  raw: string;
}

// Cap the in-memory buffer so a long-lived view holds memory flat.
const MAX_ENTRIES = 2000;
// Fixed row height — single-line rows keep windowing math exact.
const ROW_HEIGHT = 24;

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

const entries = ref<LogRow[]>([]);
const pending = ref<LogRow[]>([]);
const paused = ref(false);
const autoTail = ref(true);
const loading = ref(true);

const levelFilter = ref<string>("ALL");
const moduleFilter = ref<string>("ALL");
const search = ref("");

// ANSI SGR escapes are stripped server-side now, but lines buffered before
// that fix (or any future stray escape) get cleaned here too.
// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[[0-9;]*m/g;

// A record can carry embedded newlines: a provider logging a formatted JSON
// body, a traceback. Rows are one line tall, so a message rendered with
// `white-space: pre` painted over the rows the scroller placed after it.
const NEWLINE_RE = /\r?\n\s*/g;

let seqCounter = 0;
function toRow(entry: LogEntry): LogRow {
  const raw = entry.message.replace(ANSI_RE, "");
  return {
    ...entry,
    message: raw.trim().replace(NEWLINE_RE, " ⏎ "),
    raw,
    seq: seqCounter++,
  };
}

const levelItems = computed(() => [
  { title: t("logs.level-all"), value: "ALL" },
  ...LEVELS.map((l) => ({ title: l, value: l })),
]);

// Module options are data-driven — the backend has no fixed catalogue, so
// they're derived from whatever modules the buffered entries carry. The
// active selection is always kept in the list (even if its module has
// scrolled out of the ring buffer) so the select never goes blank.
const moduleItems = computed(() => {
  const mods = new Set<string>();
  for (const e of entries.value) {
    if (e.module) mods.add(e.module);
  }
  if (moduleFilter.value !== "ALL") mods.add(moduleFilter.value);
  return [
    { title: t("logs.module-all"), value: "ALL" },
    ...[...mods].sort().map((m) => ({ title: m, value: m })),
  ];
});

// Rank levels so "minimum severity" filtering shows the selected level
// and everything above it.
const LEVEL_RANK: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

const matchesFilters = computed(() => {
  const minRank =
    levelFilter.value === "ALL" ? 0 : (LEVEL_RANK[levelFilter.value] ?? 0);
  const mod = moduleFilter.value;
  const q = search.value.trim().toLowerCase();
  return (e: LogRow) => {
    if ((LEVEL_RANK[e.level] ?? 0) < minRank) return false;
    if (mod !== "ALL" && e.module !== mod) return false;
    return (
      !q ||
      e.raw.toLowerCase().includes(q) ||
      e.module.toLowerCase().includes(q)
    );
  };
});

// Oldest first, the order copies and downloads keep.
const filtered = computed<LogRow[]>(() =>
  entries.value.filter(matchesFilters.value),
);
// Newest first, so the latest line sits under the toolbar.
const shown = computed<LogRow[]>(() => [...filtered.value].reverse());

const scrollerRef = ref<InstanceType<typeof RVirtualScroller> | null>(null);

function getItemHeight() {
  return ROW_HEIGHT;
}
function getItemKey(item: unknown) {
  return (item as LogRow).seq;
}

function pushEntries(rows: LogRow[]) {
  if (rows.length === 0) return;
  const added = rows.filter(matchesFilters.value).length;
  const next = entries.value.concat(rows);
  // Trim the oldest once we exceed the cap; they're at the bottom.
  entries.value =
    next.length > MAX_ENTRIES ? next.slice(next.length - MAX_ENTRIES) : next;
  // New lines land above the one being read, so push the view down by as much.
  if (!autoTail.value && added > 0) {
    void nextTick(() => {
      const el = scrollerRef.value?.containerEl;
      if (el) el.scrollTop += added * ROW_HEIGHT;
    });
  }
}

useSocketEvent<LogEntry>("logs:entry", (entry) => {
  const row = toRow(entry);
  if (paused.value) {
    pending.value.push(row);
    // Bound the paused queue too so a long pause can't grow unbounded.
    if (pending.value.length > MAX_ENTRIES) {
      pending.value = pending.value.slice(pending.value.length - MAX_ENTRIES);
    }
    return;
  }
  pushEntries([row]);
});

onBeforeMount(async () => {
  try {
    const { data } = await api.get<LogEntry[]>("/logs", {
      params: { limit: 1000 },
    });
    entries.value = data.map(toRow);
  } catch {
    snackbar.error(t("logs.load-error"));
  } finally {
    loading.value = false;
  }
});

function onViewportRange(range: { first: number; last: number }) {
  // Following while the newest line is in view; scrolling down off it stops.
  autoTail.value = range.first === 0;
}

function jumpToLatest() {
  autoTail.value = true;
  scrollerRef.value?.containerEl?.scrollTo({ top: 0, behavior: "smooth" });
}

function togglePause() {
  paused.value = !paused.value;
  if (!paused.value && pending.value.length > 0) {
    const queued = pending.value;
    pending.value = [];
    pushEntries(queued);
  }
}

function clearLogs() {
  entries.value = [];
  pending.value = [];
}

function levelClass(level: string) {
  return `r-v2-logs__level--${level.toLowerCase()}`;
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString();
}

function asLine(e: LogRow) {
  return `[${new Date(e.ts).toISOString()}] ${e.level} [${e.module}] ${e.raw}`;
}

async function copyLogs() {
  try {
    await navigator.clipboard.writeText(filtered.value.map(asLine).join("\n"));
    snackbar.success(t("logs.copied"));
  } catch {
    snackbar.error(t("logs.copy-error"));
  }
}

async function copyRow(row: LogRow) {
  try {
    await navigator.clipboard.writeText(asLine(row));
    snackbar.success(t("logs.line-copied"));
  } catch {
    snackbar.error(t("logs.copy-error"));
  }
}

function downloadLogs() {
  const blob = new Blob([filtered.value.map(asLine).join("\n")], {
    type: "text/plain",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `romm-logs-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="r-v2-logs">
    <RVirtualScroller
      ref="scrollerRef"
      class="r-v2-logs__scroller"
      :items="shown"
      :get-item-height="getItemHeight"
      :get-item-key="getItemKey"
      @update:viewport-range="onViewportRange"
    >
      <template #prepend>
        <div class="r-v2-logs__toolbar">
          <RSelect
            v-model="levelFilter"
            class="r-v2-logs__level-select"
            :items="levelItems"
            item-title="title"
            item-value="value"
            density="compact"
            hide-details
            prepend-inner-icon="mdi-filter-variant"
            :aria-label="t('logs.level-filter')"
          />
          <RSelect
            v-model="moduleFilter"
            class="r-v2-logs__module-select"
            :items="moduleItems"
            item-title="title"
            item-value="value"
            density="compact"
            hide-details
            prepend-inner-icon="mdi-cube-outline"
            :aria-label="t('logs.module-filter')"
          />
          <RTextField
            v-model="search"
            class="r-v2-logs__search"
            density="compact"
            clearable
            hide-details
            prepend-inner-icon="mdi-magnify"
            :placeholder="t('logs.search-placeholder')"
            :aria-label="t('logs.search-placeholder')"
          />
          <div class="r-v2-logs__spacer" />
          <div class="r-v2-logs__actions">
            <RBtn
              :icon="paused ? 'mdi-play' : 'mdi-pause'"
              variant="text"
              density="compact"
              :color="paused ? 'primary' : undefined"
              :tooltip="paused ? t('logs.resume') : t('logs.pause')"
              :aria-label="paused ? t('logs.resume') : t('logs.pause')"
              @click="togglePause"
            />
            <RBtn
              icon="mdi-content-copy"
              variant="text"
              density="compact"
              :disabled="filtered.length === 0"
              :tooltip="t('logs.copy')"
              :aria-label="t('logs.copy')"
              @click="copyLogs"
            />
            <RBtn
              icon="mdi-download"
              variant="text"
              density="compact"
              :disabled="filtered.length === 0"
              :tooltip="t('logs.download')"
              :aria-label="t('logs.download')"
              @click="downloadLogs"
            />
            <RBtn
              icon="mdi-notification-clear-all"
              variant="text"
              density="compact"
              :disabled="entries.length === 0"
              :tooltip="t('logs.clear')"
              :aria-label="t('logs.clear')"
              @click="clearLogs"
            />
          </div>
        </div>
        <div v-if="!loading && filtered.length === 0" class="r-v2-logs__empty">
          {{ entries.length === 0 ? t("logs.empty") : t("logs.no-matches") }}
        </div>
      </template>

      <template #default="{ item, index }">
        <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -- row click is a pointer convenience for copying a single line; keyboard/AT users have the toolbar's Copy-all and Download actions -->
        <div
          class="r-v2-logs__row"
          :class="{
            'r-v2-logs__row--first': index === 0,
            'r-v2-logs__row--last': index === shown.length - 1,
          }"
          @click="copyRow(item as LogRow)"
        >
          <RTooltip
            activator="parent"
            location="top start"
            max-width="min(80vw, 900px)"
            hint-icon="mdi-content-copy"
            :text="(item as LogRow).raw"
            :hint="t('logs.click-to-copy')"
          />
          <span class="r-v2-logs__time">{{
            formatTime((item as LogRow).ts)
          }}</span>
          <span
            class="r-v2-logs__level"
            :class="levelClass((item as LogRow).level)"
            >{{ (item as LogRow).level }}</span
          >
          <span class="r-v2-logs__module">[{{ (item as LogRow).module }}]</span>
          <span class="r-v2-logs__message">{{ (item as LogRow).message }}</span>
        </div>
      </template>
    </RVirtualScroller>

    <RBtn
      v-if="!autoTail"
      class="r-v2-logs__jump"
      variant="flat"
      color="primary"
      size="small"
      prepend-icon="mdi-arrow-up"
      @click="jumpToLatest"
    >
      {{ t("logs.jump-to-latest") }}
    </RBtn>
  </div>
</template>

<style scoped>
/* Fills the Logs page's tab body; the scroller below is its only scroll, so the
   toolbar scrolls away with the lines while the page's tabs stay. */
.r-v2-logs {
  position: relative;
  min-width: 0;
  height: 100%;
  min-height: 0;
}

.r-v2-logs__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.r-v2-logs__level-select {
  width: 160px;
  flex: 0 0 auto;
}

.r-v2-logs__module-select {
  width: 160px;
  flex: 0 0 auto;
}

.r-v2-logs__search {
  width: 260px;
  flex: 0 1 auto;
}

.r-v2-logs__spacer {
  flex: 1 1 auto;
}

.r-v2-logs__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

/* Phones: the single control row overflows off the right edge. Wrap it into
   two: the level + module selectors share the first row; the search field and
   the action buttons share the second. */
html[data-bp~="sm-and-down"] .r-v2-logs__toolbar {
  flex-wrap: wrap;
}
html[data-bp~="sm-and-down"] .r-v2-logs__level-select,
html[data-bp~="sm-and-down"] .r-v2-logs__module-select {
  width: auto;
  flex: 1 1 calc(50% - 5px);
  min-width: 0;
}
html[data-bp~="sm-and-down"] .r-v2-logs__search {
  width: auto;
  /* Small, non-zero basis: >0 so it wraps off the (full) first row, small
     enough that it + the action cluster still share the second row on a 320px
     screen. It grows to fill the leftover width. */
  flex: 1 1 110px;
  min-width: 0;
}
/* Search grows to fill the second row; the action cluster sits to its right. */
html[data-bp~="sm-and-down"] .r-v2-logs__spacer {
  display: none;
}

.r-v2-logs__scroller {
  height: 100%;
}

/* The lines read as one panel: the first and last round its corners. */
.r-v2-logs__row {
  display: flex;
  align-items: center;
  gap: 10px;
  box-sizing: border-box;
  height: 24px;
  padding: 0 16px;
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-sm);
  line-height: 22px;
  white-space: nowrap;
  /* Structural guard: the row is one line tall, so anything taller would
     paint over the rows the scroller placed after it. */
  overflow: hidden;
  color: var(--r-color-fg-secondary);
  background: var(--r-color-bg-elevated);
  border-inline: 1px solid var(--r-color-border);
  cursor: pointer;
}
.r-v2-logs__row--first {
  border-top: 1px solid var(--r-color-border);
  border-start-start-radius: var(--r-radius-card);
  border-start-end-radius: var(--r-radius-card);
}
.r-v2-logs__row--last {
  border-bottom: 1px solid var(--r-color-border);
  border-end-start-radius: var(--r-radius-card);
  border-end-end-radius: var(--r-radius-card);
}

.r-v2-logs__row:hover {
  background: var(--r-color-surface-hover);
}

.r-v2-logs__time {
  flex: 0 0 auto;
  color: var(--r-color-fg-muted);
}

.r-v2-logs__level {
  flex: 0 0 72px;
  font-weight: var(--r-font-weight-bold);
  text-align: left;
}

.r-v2-logs__level--debug {
  color: var(--r-color-brand-primary);
}
.r-v2-logs__level--info {
  color: var(--r-color-status-base-success);
}
.r-v2-logs__level--warning {
  color: var(--r-color-status-base-warning);
}
.r-v2-logs__level--error,
.r-v2-logs__level--critical {
  color: var(--r-color-status-base-danger);
}

.r-v2-logs__module {
  flex: 0 0 auto;
  color: var(--r-color-fg-muted);
}

.r-v2-logs__message {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre;
  color: var(--r-color-fg);
}

.r-v2-logs__empty {
  padding: 48px 16px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  background: var(--r-color-bg-elevated);
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-md);
}

.r-v2-logs__jump {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  box-shadow: 0 4px 16px color-mix(in srgb, black 30%, transparent);
}
</style>
