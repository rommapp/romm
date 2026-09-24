<script setup lang="ts">
// EventLog: the audit log grouped by day, its filters in the URL. The list is
// windowed and pulls the next page in as its end scrolls into view.
import {
  RBtn,
  RDateField,
  REmptyState,
  RSelect,
  RSkeletonBlock,
  RSpinner,
  RTextField,
  RVirtualScroller,
} from "@v2/lib";
import { useEventListener, useResizeObserver } from "@vueuse/core";
import { isToday, isYesterday } from "date-fns";
import { debounce } from "lodash";
import { storeToRefs } from "pinia";
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type { AuditCategory, AuditEventSchema } from "@/__generated__";
import storeUsers from "@/stores/users";
import { toBrowserLocale } from "@/utils";
import EventLogRow from "@/v2/components/Settings/EventLogRow.vue";
import {
  EVENT_ROW,
  EVENT_ROW_HEIGHT,
  EVENT_ROW_VARS,
  phoneEventRowHeight,
} from "@/v2/components/Settings/eventLogLayout";
import { useAuditLog } from "@/v2/composables/useAuditLog";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useLoadingPhase } from "@/v2/composables/useLoadingPhase";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import {
  AUDIT_CATEGORIES,
  describeAuditEvent,
  type AuditEventView,
} from "@/v2/utils/auditEvents";
import { syncQueryParam } from "@/v2/utils/routeQuery";
import { canvasMeasure, wrappedLineCount } from "@/v2/utils/textLines";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const snackbar = useSnackbar();
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const { events, loading, hasMore, reset, loadMore } = useAuditLog(200);

const ALL = "all";
const DAY = /^\d{4}-\d{2}-\d{2}$/;

function queryString(key: string): string | undefined {
  const value = route.query[key];
  return typeof value === "string" && value ? value : undefined;
}

function queryDay(key: string): string | undefined {
  const value = queryString(key);
  return value && DAY.test(value) ? value : undefined;
}

const userFilter = ref<string>(queryString("user") ?? ALL);
const categoryFilter = ref<string>(queryString("category") ?? ALL);
const search = ref(queryString("q") ?? "");
const appliedSearch = ref(search.value);
const since = ref<string | undefined>(queryDay("from"));
const until = ref<string | undefined>(queryDay("to"));

const userItems = computed(() => [
  { title: t("audit.all-users"), value: ALL },
  ...allUsers.value.map((user) => ({
    title: user.username,
    value: String(user.id),
  })),
]);

const categoryItems = computed(() => [
  { title: t("audit.all-categories"), value: ALL },
  ...AUDIT_CATEGORIES.map((category) => ({
    title: t(`audit.category-${category}`),
    value: category,
  })),
]);

// The date fields hold a calendar day; the log is read from its local midnight.
function dayToDate(day: string | undefined): Date | null {
  return day ? new Date(`${day}T00:00:00Z`) : null;
}

function dateToDay(date: Date | null): string | undefined {
  return date ? date.toISOString().slice(0, 10) : undefined;
}

function localMidnight(day: string, addDays = 0): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date + addDays).toISOString();
}

const sinceDate = computed({
  get: () => dayToDate(since.value),
  set: (date) => (since.value = dateToDay(date)),
});
const untilDate = computed({
  get: () => dayToDate(until.value),
  set: (date) => (until.value = dateToDay(date)),
});

// Typing searches once it pauses, as the gallery's search does.
const applySearch = debounce(() => {
  appliedSearch.value = search.value.trim();
}, 300);
watch(search, applySearch);
onBeforeUnmount(() => applySearch.cancel());

const hasFilters = computed(
  () =>
    userFilter.value !== ALL ||
    categoryFilter.value !== ALL ||
    !!appliedSearch.value ||
    !!since.value ||
    !!until.value,
);

// Set when a page fails to load, so scrolling doesn't retry it on every frame.
const moreFailed = ref(false);

async function refresh() {
  moreFailed.value = false;
  try {
    await reset({
      actorIds:
        userFilter.value === ALL ? undefined : [Number(userFilter.value)],
      categories:
        categoryFilter.value === ALL
          ? undefined
          : [categoryFilter.value as AuditCategory],
      search: appliedSearch.value,
      since: since.value ? localMidnight(since.value) : undefined,
      // Inclusive of the whole day picked.
      until: until.value ? localMidnight(until.value, 1) : undefined,
    });
  } catch {
    snackbar.error(t("audit.load-error"));
  }
}

function searchNow() {
  applySearch.cancel();
  const next = search.value.trim();
  // Searching the same text again reloads, picking up newer events.
  if (next === appliedSearch.value) void refresh();
  else appliedSearch.value = next;
}

async function showMore() {
  moreFailed.value = false;
  try {
    await loadMore();
  } catch {
    moreFailed.value = true;
  }
}

watch(
  [userFilter, categoryFilter, appliedSearch, since, until],
  ([user, category, q, from, to]) => {
    syncQueryParam(router, "user", user === ALL ? undefined : user);
    syncQueryParam(router, "category", category === ALL ? undefined : category);
    syncQueryParam(router, "q", q || undefined);
    syncQueryParam(router, "from", from);
    syncQueryParam(router, "to", to);
    void refresh();
  },
);

onMounted(async () => {
  void refresh();
  try {
    await usersStore.ensureLoaded();
  } catch (error) {
    console.error("Could not load users:", error);
  }
});

const phase = useLoadingPhase(
  () => loading.value,
  () => events.value.length === 0,
);

const timeFormat = computed(
  () =>
    new Intl.DateTimeFormat(toBrowserLocale(locale.value), {
      hour: "2-digit",
      minute: "2-digit",
    }),
);

const dayFormats = computed(() => {
  const intlLocale = toBrowserLocale(locale.value);
  const format = { weekday: "long", day: "numeric", month: "long" } as const;
  return {
    thisYear: new Intl.DateTimeFormat(intlLocale, format),
    otherYear: new Intl.DateTimeFormat(intlLocale, {
      ...format,
      year: "numeric",
    }),
  };
});

function dayLabel(date: Date, year: number): string {
  if (isToday(date)) return t("common.today");
  if (isYesterday(date)) return t("audit.yesterday");
  const { thisYear, otherYear } = dayFormats.value;
  return (date.getFullYear() === year ? thisYear : otherYear).format(date);
}

// Each page brings the earlier ones along, so their sentences are kept rather
// than rebuilt; the cache starts over with the language.
const described = computed(() => {
  void locale.value;
  return new WeakMap<AuditEventSchema, AuditEventView>();
});

function describe(event: AuditEventSchema): AuditEventView {
  let view = described.value.get(event);
  if (!view) {
    view = describeAuditEvent(event);
    described.value.set(event, view);
  }
  return view;
}

interface EventItem {
  kind: "event";
  key: number;
  event: AuditEventSchema;
  view: AuditEventView;
  first: boolean;
  last: boolean;
  height: number;
}

interface DayItem {
  kind: "day";
  key: string;
  label: string;
}

type Item = DayItem | EventItem | { kind: "more"; key: "more" };

// Kept in step with the day and "more" rows below.
const ROW_HEIGHTS = { day: 44, more: 56 } as const;

// A phone wraps each event's title and detail, so its row's height depends on
// how they wrap in the fonts and width of a row already on screen.
interface TextMetrics {
  width: number;
  fonts: string;
  title: (run: string) => number;
  detail: (run: string) => number;
}

const listRoot = ref<HTMLElement | null>(null);
const scroller = ref<InstanceType<typeof RVirtualScroller> | null>(null);
const { xs } = useBreakpoint();
const textMetrics = shallowRef<TextMetrics | null>(null);

function readTextMetrics(force = false) {
  if (!xs.value) return;
  const body = listRoot.value?.querySelector<HTMLElement>(
    ".r-v2-audit-event__body",
  );
  const title = body?.querySelector<HTMLElement>(".r-v2-audit-event__title");
  const meta = body?.querySelector<HTMLElement>(".r-v2-audit-event__meta");
  if (!body || !title || !meta) return;
  const width = body.clientWidth;
  const current = textMetrics.value;
  if (!force && current?.width === width) return;
  const titleFont = getComputedStyle(title).font;
  const metaFont = getComputedStyle(meta).font;
  const fonts = `${titleFont}|${metaFont}`;
  // Measurers remember word widths, so they're kept while the fonts are.
  if (!force && current?.fonts === fonts) {
    textMetrics.value = { ...current, width };
    return;
  }
  const measureTitle = canvasMeasure(titleFont);
  const measureDetail = canvasMeasure(metaFont);
  if (!measureTitle || !measureDetail) return;
  textMetrics.value = {
    width,
    fonts,
    title: measureTitle,
    detail: measureDetail,
  };
}

function phoneLines(text: string, font: "title" | "detail"): number {
  const metrics = textMetrics.value;
  if (!metrics) return 1;
  // Measured a little short, so a line that only just fits counts as wrapped:
  // a spare line is better than one cut off.
  return wrappedLineCount(
    text,
    metrics.width - 2,
    metrics[font],
    EVENT_ROW.maxLines,
  );
}

// Like the sentences, heights are kept until the fonts or the width change.
const heights = computed(() => {
  void textMetrics.value;
  return new WeakMap<AuditEventView, number>();
});

function eventHeight(event: AuditEventSchema, view: AuditEventView): number {
  if (!xs.value) return EVENT_ROW_HEIGHT;
  let height = heights.value.get(view);
  if (height === undefined) {
    height = phoneEventRowHeight({
      title: phoneLines(view.title, "title"),
      detail: view.detail ? phoneLines(view.detail, "detail") : 0,
      where: !!(event.device_name || event.ip_address),
    });
    heights.value.set(view, height);
  }
  return height;
}

// Events arrive newest first, so each local day is one run of them. Nothing is
// handed to the scroller until the list is shown.
const items = computed<Item[]>(() => {
  if (phase.value !== "content") return [];
  const year = new Date().getFullYear();
  const out: Item[] = [];
  let dayKey: string | null = null;
  let previous: EventItem | null = null;
  for (const event of events.value) {
    const date = new Date(event.occurred_at);
    const key = date.toDateString();
    const startsDay = key !== dayKey;
    if (startsDay) {
      if (previous) previous.last = true;
      dayKey = key;
      out.push({ kind: "day", key: `day-${key}`, label: dayLabel(date, year) });
    }
    const view = describe(event);
    previous = {
      kind: "event",
      key: event.id,
      event,
      view,
      first: startsDay,
      last: false,
      height: eventHeight(event, view),
    };
    out.push(previous);
  }
  if (previous) previous.last = true;
  if (hasMore.value) out.push({ kind: "more", key: "more" });
  return out;
});

function itemHeight(item: unknown): number {
  const row = item as Item;
  return row.kind === "event" ? row.height : ROW_HEIGHTS[row.kind];
}

function itemKey(item: unknown): string | number {
  return (item as Item).key;
}

function onViewportRange({ last }: { first: number; last: number }) {
  if (hasMore.value && !moreFailed.value && last >= items.value.length - 20) {
    void showMore();
  }
}

useGridNav(listRoot, {
  rowSelector: ".r-v2-audit-event",
  getCells: (row) => Array.from(row.querySelectorAll<HTMLElement>("a")),
});

watch(items, () => readTextMetrics(), { flush: "post" });
// The scroller's content box leaves out its scrollbar, so it narrows with one.
useResizeObserver(
  () => scroller.value?.containerEl,
  () => readTextMetrics(),
);
// A web font loaded after a measure changes the widths under the same name.
useEventListener(document.fonts, "loadingdone", (event) => {
  const fonts = textMetrics.value?.fonts;
  const loaded = (event as FontFaceSetLoadEvent).fontfaces;
  if (
    fonts &&
    loaded.some((f) => fonts.includes(f.family.replace(/["']/g, "")))
  ) {
    readTextMetrics(true);
  }
});
</script>

<template>
  <div ref="listRoot" class="r-v2-audit" :style="EVENT_ROW_VARS">
    <RVirtualScroller
      ref="scroller"
      class="r-v2-audit__scroller"
      :items="items"
      :get-item-height="itemHeight"
      :get-item-key="itemKey"
      @update:viewport-range="onViewportRange"
    >
      <template #prepend>
        <div class="r-v2-audit__toolbar">
          <RSelect
            v-model="userFilter"
            class="r-v2-audit__select"
            :items="userItems"
            item-title="title"
            item-value="value"
            density="compact"
            hide-details
            searchable
            prepend-inner-icon="mdi-account-outline"
            :aria-label="t('audit.filter-user')"
          />
          <RSelect
            v-model="categoryFilter"
            class="r-v2-audit__select"
            :items="categoryItems"
            item-title="title"
            item-value="value"
            density="compact"
            hide-details
            prepend-inner-icon="mdi-filter-variant"
            :aria-label="t('audit.filter-category')"
          />
          <div class="r-v2-audit__range">
            <div class="r-v2-audit__date">
              <RDateField
                v-model="sinceDate"
                density="compact"
                hide-details
                clearable
                :max="untilDate"
                :placeholder="t('audit.since')"
                :aria-label="t('audit.since')"
              />
            </div>
            <div class="r-v2-audit__date">
              <RDateField
                v-model="untilDate"
                density="compact"
                hide-details
                clearable
                :min="sinceDate"
                :placeholder="t('audit.until')"
                :aria-label="t('audit.until')"
              />
            </div>
          </div>
          <RTextField
            v-model="search"
            class="r-v2-audit__search"
            density="compact"
            clearable
            hide-details
            prepend-inner-icon="mdi-magnify"
            :placeholder="t('audit.search-placeholder')"
            :aria-label="t('audit.search-placeholder')"
            @keyup.enter="searchNow"
          />
        </div>

        <div v-if="phase === 'skeleton'" class="r-v2-audit__skeleton">
          <RSkeletonBlock
            v-for="n in 8"
            :key="`sk-${n}`"
            width="100%"
            height="54px"
            rounded="lg"
          />
        </div>
        <REmptyState
          v-else-if="phase === 'empty'"
          icon="mdi-timeline-clock-outline"
          :title="hasFilters ? t('audit.no-matches') : t('audit.empty')"
        />
      </template>

      <template #default="{ item }">
        <h3 v-if="(item as Item).kind === 'day'" class="r-v2-audit-day">
          {{ (item as DayItem).label }}
        </h3>
        <div
          v-else-if="(item as Item).kind === 'more'"
          class="r-v2-audit__more"
        >
          <RSpinner v-if="!moreFailed" :size="22" />
          <RBtn
            v-else
            variant="text"
            prepend-icon="mdi-refresh"
            @click="showMore"
          >
            {{ t("audit.load-error") }}
          </RBtn>
        </div>
        <EventLogRow
          v-else-if="(item as Item).kind === 'event'"
          :event="(item as EventItem).event"
          :view="(item as EventItem).view"
          :first="(item as EventItem).first"
          :last="(item as EventItem).last"
          :height="(item as EventItem).height"
          :time="
            timeFormat.format(new Date((item as EventItem).event.occurred_at))
          "
        />
      </template>
    </RVirtualScroller>
  </div>
</template>

<style scoped>
/* The Logs page pins to the viewport, so the event log scrolls inside it:
   the toolbar scrolls away with the events, the page's tabs stay. */
.r-v2-audit {
  height: 100%;
  min-height: 0;
}

.r-v2-audit__scroller {
  height: 100%;
}

.r-v2-audit__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--r-space-2);
}

.r-v2-audit__select {
  width: 190px;
  flex: 0 0 auto;
}

.r-v2-audit__range {
  display: flex;
  gap: 10px;
  flex: 0 0 auto;
  min-width: 0;
}

.r-v2-audit__date {
  width: 160px;
  min-width: 0;
}

.r-v2-audit__search {
  flex: 1 1 200px;
  min-width: 0;
}

html[data-bp~="sm-and-down"] .r-v2-audit__select {
  width: auto;
  flex: 1 1 calc(50% - 5px);
  min-width: 0;
}
/* The range keeps both ends on one row, sharing the full width. */
html[data-bp~="sm-and-down"] .r-v2-audit__range {
  flex: 1 1 100%;
}
html[data-bp~="sm-and-down"] .r-v2-audit__date {
  width: auto;
  flex: 1 1 0;
}

.r-v2-audit__skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-v2-audit-day {
  display: flex;
  align-items: flex-end;
  box-sizing: border-box;
  height: 44px;
  margin: 0;
  padding: 0 var(--r-space-1) var(--r-space-2);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

/* Weekday names are lowercase in many languages. */
.r-v2-audit-day::first-letter {
  text-transform: uppercase;
}

.r-v2-audit__more {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
}
</style>
