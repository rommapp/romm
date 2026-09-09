<script setup lang="ts">
// AnniversaryWidget: games released on today's date in an earlier year, one at
// a time, with arrows to page through the rest. It reads the shared rom list
// with `releasedDays`, one page at a time, so the day's whole result set never
// crosses the wire for a card that shows one game.
//
// The calendar policy lives here rather than server-side: `anniversaryQuery`
// picks the days and the year bound off the client's own clock, so "today" is
// the date in front of the user and no timezone skew can reach it.
import { RBtn } from "@v2/lib";
import { anniversaryQuery, releaseYear } from "@v2/utils/time";
import { useIntervalFn } from "@vueuse/core";
import { computed, nextTick, onMounted, ref } from "vue";
import type { ComponentPublicInstance, Ref } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import WidgetCard from "./WidgetCard.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

// A Home page can sit open across local midnight, and the card is pinned to a
// date, so the day it was loaded for is compared against the clock.
const DAY_ROLLOVER_CHECK_MS = 60_000;

// Far more cards than anyone clicks through in a sitting, so one request
// normally covers the whole visit, and small enough that a day holding
// hundreds of games never ships them all.
const PAGE_SIZE = 24;

type DayQuery = NonNullable<ReturnType<typeof anniversaryQuery>>;

// The day's oldest releases, accumulated a page at a time, so paging backwards
// is always in memory and only moving past the end fetches.
const roms = ref<SimpleRom[]>([]);
const total = ref(0);
const loadedDay = ref("");
const dayQuery = ref<DayQuery | null>(null);
const index = ref(0);
const loading = ref(false);
const paging = ref(false);
const failed = ref(false);
const prevBtn = ref<ComponentPublicInstance | null>(null);
const nextBtn = ref<ComponentPublicInstance | null>(null);

const current = computed<SimpleRom | null>(
  () => roms.value[index.value] ?? null,
);

const title = computed(
  () => current.value?.name || current.value?.fs_name || "",
);

const atStart = computed(() => index.value <= 0);
const atEnd = computed(() => index.value >= total.value - 1);

// The query already excludes the viewer's current year; this keeps a client
// whose clock disagrees with the server's from rendering "0 years ago".
const yearsAgo = computed(() => {
  const released = releaseYear(current.value?.metadatum?.first_release_date);
  if (!released) return null;
  const years = new Date().getFullYear() - released;
  return years >= 1 ? years : null;
});

const placeholder = computed(() =>
  failed.value
    ? t("home.widget-anniversaries-error")
    : t("home.widget-anniversaries-empty"),
);

function btnEl(btn: Ref<ComponentPublicInstance | null>): HTMLElement | null {
  return (btn.value?.$el as HTMLElement | undefined) ?? null;
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

function fetchPage(query: DayQuery, offset: number) {
  return romApi.getRoms({
    releasedDays: query.days,
    releasedBeforeYear: query.beforeYear,
    orderBy: "first_release_date",
    orderDir: "asc",
    limit: PAGE_SIZE,
    offset,
    // The counter needs the day's total once; a later page already has it.
    withTotal: offset === 0,
    // The card renders a cover, a title, a platform and a year. None of the
    // gallery's sidecars reach it, and each one is its own scan.
    withCharIndex: false,
    withFilterValues: false,
    withRomIdIndex: false,
  });
}

async function load() {
  // The client's own calendar day, so "today" matches the date in front of
  // the user rather than the server's UTC clock.
  const today = new Date();
  const day = dayKey(today);
  loadedDay.value = day;
  // A request spanning midnight can land after the rollover's. Committing it
  // would pin the card to yesterday until the next rollover, a day away.
  const stale = () => loadedDay.value !== day;

  const query = anniversaryQuery(today);
  dayQuery.value = query;
  if (!query) {
    // 1 January says nothing about a release date, so there is nothing to ask.
    roms.value = [];
    total.value = 0;
    index.value = 0;
    failed.value = false;
    loading.value = false;
    return;
  }

  loading.value = true;
  try {
    const { data } = await fetchPage(query, 0);
    if (stale()) return;
    roms.value = data.items;
    total.value = data.total ?? data.items.length;
    index.value = 0;
    failed.value = false;
    loading.value = false;
  } catch {
    if (stale()) return;
    // Failures show in the card's own copy rather than the snackbar stack.
    roms.value = [];
    total.value = 0;
    failed.value = true;
    loading.value = false;
    // Leave the day unclaimed so the rollover check retries it. Claimed, a
    // single failed request would hold the error copy until local midnight.
    loadedDay.value = "";
  }
}

/** Appends the next page. A failure keeps the current card and lets the arrow retry. */
async function loadMore() {
  const query = dayQuery.value;
  const day = loadedDay.value;
  if (!query || paging.value) return;

  paging.value = true;
  try {
    const { data } = await fetchPage(query, roms.value.length);
    if (loadedDay.value !== day) return;
    roms.value = [...roms.value, ...data.items];
    total.value = data.total ?? total.value;
  } catch {
    // Swallowed: the loaded card is still good, and the arrow stays live.
  } finally {
    if (loadedDay.value === day) paging.value = false;
  }
}

async function step(delta: number) {
  const target = index.value + delta;
  if (target < 0 || target >= total.value) return;

  const back = delta < 0;
  const moved = back ? prevBtn : nextBtn;
  const other = back ? nextBtn : prevBtn;
  const hadFocus = document.activeElement === btnEl(moved);

  if (target >= roms.value.length) {
    await loadMore();
    if (target >= roms.value.length) return;
  }

  index.value = target;

  // Reaching an end disables the arrow that got you there, which pulls focus to
  // <body>; hand it to the arrow that still works.
  if (hadFocus && (back ? atStart.value : atEnd.value)) {
    await nextTick();
    btnEl(other)?.focus();
  }
}

onMounted(load);

useIntervalFn(() => {
  if (dayKey(new Date()) !== loadedDay.value) void load();
}, DAY_ROLLOVER_CHECK_MS);
</script>

<template>
  <WidgetCard :title="t('home.widget-anniversaries')" :loading="loading">
    <template #action>
      <div class="r-v2-widget-anniv__nav">
        <RBtn
          ref="prevBtn"
          variant="text"
          size="x-small"
          icon="mdi-chevron-left"
          :disabled="atStart"
          :tooltip="t('home.widget-anniversaries-prev')"
          :aria-label="t('home.widget-anniversaries-prev')"
          @click="step(-1)"
        />
        <RBtn
          ref="nextBtn"
          variant="text"
          size="x-small"
          icon="mdi-chevron-right"
          :disabled="atEnd"
          :loading="paging"
          :tooltip="t('home.widget-anniversaries-next')"
          :aria-label="t('home.widget-anniversaries-next')"
          @click="step(1)"
        />
      </div>
    </template>
    <router-link
      v-if="current"
      class="r-v2-widget-anniv__body"
      :to="{ name: ROUTES.ROM, params: { rom: current.id } }"
    >
      <GameCover
        :rom="current"
        :title="title"
        :identified="current.is_identified"
        class="r-v2-widget-anniv__cover"
      />
      <div class="r-v2-widget-anniv__info">
        <div class="r-v2-widget-anniv__name">{{ title }}</div>
        <div class="r-v2-widget-anniv__platform">
          <CachedPlatformIcon
            :slug="current.platform_slug"
            :name="current.platform_display_name"
            :size="14"
          />
          <span class="r-v2-widget-anniv__platform-name">
            {{ current.platform_display_name }}
          </span>
        </div>
        <div class="r-v2-widget-anniv__meta">
          <span v-if="yearsAgo">
            {{ t("home.widget-anniversaries-years", { count: yearsAgo }) }}
          </span>
          <span v-if="total > 1" class="r-v2-widget-anniv__position">
            {{ index + 1 }} / {{ total }}
          </span>
        </div>
      </div>
    </router-link>
    <div v-else class="r-v2-widget-anniv__empty">
      {{ placeholder }}
    </div>
  </WidgetCard>
</template>

<style scoped>
.r-v2-widget-anniv__nav {
  display: flex;
  align-items: center;
  gap: 2px;
}

.r-v2-widget-anniv__body {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
  border-radius: var(--r-radius-sm);
}

/* Fixed height, natural width, so the cover renders at its image's true aspect
   (GameCover measures it), matching the gallery. The descendant selector
   outweighs GameCover's base `width: 100%` so width can follow the ratio. */
.r-v2-widget-anniv__body .r-v2-widget-anniv__cover {
  height: 70px;
  width: auto;
  flex-shrink: 0;
  --r-cover-radius: var(--r-radius-sm);
}

.r-v2-widget-anniv__info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-widget-anniv__name {
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.2;
  color: var(--r-color-fg);
  /* Clamped at 2 lines, like RandomPick, so the rail's heights stay in step. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Hover is gated to pointer modalities so a parked cursor doesn't compete with
   the focused element under keyboard / gamepad. */
html[data-input="mouse"]
  .r-v2-widget-anniv__body:hover
  .r-v2-widget-anniv__name,
html[data-input="touch"]
  .r-v2-widget-anniv__body:hover
  .r-v2-widget-anniv__name,
.r-v2-widget-anniv__body:focus-visible .r-v2-widget-anniv__name {
  color: var(--r-color-brand-primary);
}

.r-v2-widget-anniv__platform {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-widget-anniv__platform-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-widget-anniv__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: auto;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-v2-widget-anniv__position {
  margin-left: auto;
  color: var(--r-color-fg-faint);
}

.r-v2-widget-anniv__empty {
  font-size: 12px;
  color: var(--r-color-fg-faint);
  margin-top: auto;
}
</style>
