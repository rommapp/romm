<script setup lang="ts">
// AuditLog: what every user, and RomM itself, did, newest first. Filters live
// in the URL so a view of the log can be shared.
import {
  RAvatar,
  RBtn,
  RDateField,
  REmptyState,
  RIcon,
  RSelect,
  RSkeletonBlock,
  RTextField,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink, useRoute, useRouter } from "vue-router";
import type { AuditCategory, AuditEventSchema } from "@/__generated__";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import AssetTimestamp from "@/v2/components/shared/AssetTimestamp.vue";
import { useAuditLog } from "@/v2/composables/useAuditLog";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useLoadingPhase } from "@/v2/composables/useLoadingPhase";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import {
  AUDIT_CATEGORIES,
  describeAuditEvent,
  type AuditEventView,
} from "@/v2/utils/auditEvents";
import { syncQueryParam } from "@/v2/utils/routeQuery";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const snackbar = useSnackbar();
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const { events, loading, loadingMore, hasMore, reset, loadMore } =
  useAuditLog();

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

// Emptying the box shows everything again; anything else waits for a search.
watch(search, (value) => {
  if (!value.trim()) appliedSearch.value = "";
});

const hasFilters = computed(
  () =>
    userFilter.value !== ALL ||
    categoryFilter.value !== ALL ||
    !!appliedSearch.value ||
    !!since.value ||
    !!until.value,
);

async function refresh() {
  try {
    await reset({
      actorIds:
        userFilter.value === ALL ? undefined : [Number(userFilter.value)],
      categories:
        categoryFilter.value === ALL
          ? undefined
          : [categoryFilter.value as AuditCategory],
      search: appliedSearch.value || undefined,
      since: since.value ? localMidnight(since.value) : undefined,
      // Inclusive of the whole day picked.
      until: until.value ? localMidnight(until.value, 1) : undefined,
    });
  } catch {
    snackbar.error(t("audit.load-error"));
  }
}

function submitSearch() {
  const next = search.value.trim();
  // Searching the same text again reloads, picking up newer events.
  if (next === appliedSearch.value) void refresh();
  else appliedSearch.value = next;
}

async function showMore() {
  try {
    await loadMore();
  } catch {
    snackbar.error(t("audit.load-error"));
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
  if (allUsers.value.length > 0) return;
  try {
    const { data } = await userApi.fetchUsers();
    usersStore.set(data);
  } catch (error) {
    console.error("Could not load users:", error);
  }
});

interface Row {
  event: AuditEventSchema;
  view: AuditEventView;
}

const rows = computed<Row[]>(() =>
  events.value.map((event) => ({ event, view: describeAuditEvent(event) })),
);

const phase = useLoadingPhase(
  () => loading.value,
  () => rows.value.length === 0,
);

const listRoot = ref<HTMLElement | null>(null);
useGridNav(listRoot, {
  rowSelector: ".r-v2-audit-event",
  getCells: (row) => Array.from(row.querySelectorAll<HTMLElement>("a")),
});

function actorName(event: AuditEventSchema): string {
  if (event.actor_kind === "system") return t("audit.system");
  if (event.actor_kind === "anonymous") return t("audit.anonymous");
  return event.actor?.username ?? event.actor_name ?? t("audit.deleted-user");
}

function actorIcon(event: AuditEventSchema): string | undefined {
  if (event.actor_kind === "system") return "mdi-robot-outline";
  if (event.actor_kind === "anonymous") return "mdi-incognito";
  return event.actor ? undefined : "mdi-account-off-outline";
}

function actorAvatar(event: AuditEventSchema): string | undefined {
  if (!event.actor) return undefined;
  return userAvatarUrl({
    userId: event.actor.id,
    avatarPath: event.actor.avatar_path,
    updatedAt: event.actor.updated_at,
  });
}
</script>

<template>
  <div class="r-v2-audit">
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
        @keyup.enter="submitSearch"
      />
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-magnify"
        :loading="loading"
        @click="submitSearch"
      >
        {{ t("common.search") }}
      </RBtn>
    </div>

    <div v-if="phase === 'skeleton'" class="r-v2-audit__list">
      <RSkeletonBlock
        v-for="n in 8"
        :key="`sk-${n}`"
        width="100%"
        height="76px"
        rounded="lg"
      />
    </div>

    <REmptyState
      v-else-if="phase === 'empty'"
      icon="mdi-clipboard-text-clock-outline"
      :title="hasFilters ? t('audit.no-matches') : t('audit.empty')"
    />

    <ul v-else-if="phase === 'content'" ref="listRoot" class="r-v2-audit__list">
      <li
        v-for="{ event, view } in rows"
        :key="event.id"
        class="r-v2-audit-event"
      >
        <component
          :is="view.to ? RouterLink : 'div'"
          :to="view.to ?? undefined"
          class="r-v2-audit-event__main"
        >
          <RAvatar
            :icon="view.icon"
            :color="view.tone"
            variant="translucent"
            size="36"
            class="r-v2-audit-event__icon"
          />
          <span class="r-v2-audit-event__text">
            <span class="r-v2-audit-event__title">{{ view.title }}</span>
            <span v-if="view.detail" class="r-v2-audit-event__detail">
              {{ view.detail }}
            </span>
            <span class="r-v2-audit-event__meta">
              <span class="r-v2-audit-event__meta-item">
                <RAvatar
                  :image="actorAvatar(event)"
                  :icon="actorIcon(event)"
                  variant="translucent"
                  size="16"
                />
                {{ actorName(event) }}
              </span>
              <span
                v-if="event.device_name"
                class="r-v2-audit-event__meta-item"
              >
                <RIcon icon="mdi-devices" size="14" />
                {{ event.device_name }}
              </span>
              <span
                v-if="event.ip_address"
                class="r-v2-audit-event__meta-item r-v2-audit-event__ip"
              >
                <RIcon icon="mdi-ip-network-outline" size="14" />
                {{ event.ip_address }}
              </span>
            </span>
          </span>
          <AssetTimestamp
            :date="event.occurred_at"
            stacked
            class="r-v2-audit-event__time"
          />
        </component>
      </li>
    </ul>

    <div v-if="hasMore && phase === 'content'" class="r-v2-audit__more">
      <RBtn variant="text" :loading="loadingMore" @click="showMore">
        {{ t("audit.load-more") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-audit {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.r-v2-audit__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
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

.r-v2-audit__list {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.r-v2-audit-event {
  border-radius: var(--r-radius-card);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}

.r-v2-audit-event__main {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-3) var(--r-space-4);
  border-radius: var(--r-radius-card);
  color: inherit;
  text-decoration: none;
}

a.r-v2-audit-event__main:hover {
  background: var(--r-color-surface-hover);
}

.r-v2-audit-event__icon {
  flex-shrink: 0;
}

.r-v2-audit-event__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-audit-event__title {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  overflow-wrap: anywhere;
}

.r-v2-audit-event__detail {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  overflow-wrap: anywhere;
}

.r-v2-audit-event__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px var(--r-space-3);
  margin-top: 2px;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

.r-v2-audit-event__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.r-v2-audit-event__ip {
  font-family: var(--r-font-family-mono);
}

/* On a phone the time moves under the text so the sentence keeps the width. */
html[data-bp~="xs"] .r-v2-audit-event__main {
  flex-wrap: wrap;
  row-gap: var(--r-space-1);
}
html[data-bp~="xs"] .r-v2-audit-event__time {
  order: 3;
  flex-basis: 100%;
  flex-direction: row;
  align-items: baseline;
  padding-left: calc(36px + var(--r-space-3));
}

.r-v2-audit__more {
  display: flex;
  justify-content: center;
}
</style>
