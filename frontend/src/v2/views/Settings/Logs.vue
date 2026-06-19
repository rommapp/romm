<script setup lang="ts">
// Logs — admin-only real-time backend log viewer.
//
// On open it backfills the last N buffered lines from `GET /logs`, then
// streams new lines live over Socket.IO (`logs:entry`, emitted to the
// `admin` room by the backend forwarder). State is view-scoped and
// ephemeral (constitution §VI.D): a capped in-memory ring buffer, no
// store, no global lifecycle — backfill covers re-open.
//
// The list is windowed with RVirtualScroller. Rows are single-line
// monospace (terminal style) and scroll horizontally for long lines; the
// full message is also surfaced on hover via RTooltip. Auto-tail follows
// the newest line and pauses itself when the user scrolls up; "jump to
// latest" re-engages it.
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
const search = ref("");

// ANSI SGR escapes are stripped server-side now, but lines buffered before
// that fix (or any future stray escape) get cleaned here too.
// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[[0-9;]*m/g;

let seqCounter = 0;
function toRow(entry: LogEntry): LogRow {
  return {
    ...entry,
    message: entry.message.replace(ANSI_RE, ""),
    seq: seqCounter++,
  };
}

const levelItems = computed(() => [
  { title: t("logs.level-all"), value: "ALL" },
  ...LEVELS.map((l) => ({ title: l, value: l })),
]);

// Rank levels so "minimum severity" filtering shows the selected level
// and everything above it.
const LEVEL_RANK: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

const filtered = computed<LogRow[]>(() => {
  const minRank =
    levelFilter.value === "ALL" ? 0 : (LEVEL_RANK[levelFilter.value] ?? 0);
  const q = search.value.trim().toLowerCase();
  return entries.value.filter((e) => {
    if ((LEVEL_RANK[e.level] ?? 0) < minRank) return false;
    if (
      q &&
      !e.message.toLowerCase().includes(q) &&
      !e.module.toLowerCase().includes(q)
    ) {
      return false;
    }
    return true;
  });
});

const scrollerRef = ref<InstanceType<typeof RVirtualScroller> | null>(null);

function getItemHeight() {
  return ROW_HEIGHT;
}
function getItemKey(item: unknown) {
  return (item as LogRow).seq;
}

function scrollToBottom(smooth = false) {
  nextTick(() => {
    const n = filtered.value.length;
    if (n > 0) scrollerRef.value?.scrollToIndex(n - 1, { smooth });
  });
}

function pushEntries(rows: LogRow[]) {
  if (rows.length === 0) return;
  const next = entries.value.concat(rows);
  // Trim from the front once we exceed the cap.
  entries.value =
    next.length > MAX_ENTRIES ? next.slice(next.length - MAX_ENTRIES) : next;
  if (autoTail.value) scrollToBottom();
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
    scrollToBottom();
  } catch {
    snackbar.error(t("logs.load-error"));
  } finally {
    loading.value = false;
  }
});

function onViewportRange(range: { first: number; last: number }) {
  // Treat "the last row is visible" as being parked at the bottom; any
  // scroll-up off the tail disengages auto-follow.
  const n = filtered.value.length;
  autoTail.value = n === 0 || range.last >= n - 1;
}

function jumpToLatest() {
  autoTail.value = true;
  scrollToBottom(true);
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
  return `[${new Date(e.ts).toISOString()}] ${e.level} [${e.module}] ${e.message}`;
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
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="r-v2-logs">
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

    <div class="r-v2-logs__panel">
      <RVirtualScroller
        ref="scrollerRef"
        class="r-v2-logs__scroller"
        :style="{ overflowX: 'auto' }"
        :items="filtered"
        :get-item-height="getItemHeight"
        :get-item-key="getItemKey"
        @update:viewport-range="onViewportRange"
      >
        <template #default="{ item }">
          <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -- row click is a pointer convenience for copying a single line; keyboard/AT users have the toolbar's Copy-all and Download actions -->
          <div class="r-v2-logs__row" @click="copyRow(item as LogRow)">
            <RTooltip
              activator="parent"
              location="top start"
              max-width="min(80vw, 900px)"
              hint-icon="mdi-content-copy"
              :text="(item as LogRow).message"
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
            <span class="r-v2-logs__module"
              >[{{ (item as LogRow).module }}]</span
            >
            <span class="r-v2-logs__message">{{
              (item as LogRow).message
            }}</span>
          </div>
        </template>
      </RVirtualScroller>

      <div v-if="!loading && filtered.length === 0" class="r-v2-logs__empty">
        {{ entries.length === 0 ? t("logs.empty") : t("logs.no-matches") }}
      </div>

      <RBtn
        v-if="!autoTail"
        class="r-v2-logs__jump"
        variant="flat"
        color="primary"
        size="small"
        prepend-icon="mdi-arrow-down"
        @click="jumpToLatest"
      >
        {{ t("logs.jump-to-latest") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-logs {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  /* Fill the SettingsLayout `fill` body so the panel reaches the bottom of
     the viewport and the scroll lives inside the panel, not the document. */
  height: 100%;
  min-height: 0;
}

.r-v2-logs__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.r-v2-logs__level-select {
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

.r-v2-logs__panel {
  position: relative;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
}

.r-v2-logs__scroller {
  height: 100%;
  padding: 8px 0;
}

.r-v2-logs__row {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 24px;
  /* Wider than the viewport when the line is long — the scroller scrolls
     horizontally (overflow-x:auto inline) to reveal the full message
     instead of truncating it. */
  width: max-content;
  min-width: 100%;
  padding: 0 16px;
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-sm);
  line-height: 24px;
  white-space: nowrap;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
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
  flex: 0 0 auto;
  white-space: pre;
  color: var(--r-color-fg);
}

.r-v2-logs__empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-md);
  pointer-events: none;
}

.r-v2-logs__jump {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  box-shadow: 0 4px 16px color-mix(in srgb, black 30%, transparent);
}
</style>
