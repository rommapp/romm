<script setup lang="ts">
// AuditLog: what every user, and RomM itself, did, newest first. Filters live
// in the URL so a view of the log can be shared.
import {
  RAvatar,
  RBtn,
  RDateField,
  RSelect,
  RTable,
  RTextField,
  type RTableColumn,
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

const columns = computed<RTableColumn[]>(() => [
  {
    key: "when",
    label: t("audit.col-when"),
    width: "150px",
    skeletonWidth: 110,
  },
  {
    key: "who",
    label: t("audit.col-who"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 120,
  },
  {
    key: "what",
    label: t("audit.col-what"),
    width: "minmax(0, 2.6fr)",
    skeletonWidth: 240,
  },
  {
    key: "device",
    label: t("audit.col-device"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 100,
  },
]);

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

    <RTable
      :columns="columns"
      :items="rows"
      :item-key="(row) => (row as Row).event.id"
      :loading="loading && rows.length === 0"
      :loading-rows="10"
      empty-icon="mdi-clipboard-text-clock-outline"
      :empty-message="hasFilters ? t('audit.no-matches') : t('audit.empty')"
    >
      <template #cell.when="{ row }">
        <AssetTimestamp :date="(row as Row).event.occurred_at" stacked />
      </template>
      <template #cell.who="{ row }">
        <span class="r-v2-audit__who">
          <RAvatar
            :image="actorAvatar((row as Row).event)"
            :icon="actorIcon((row as Row).event)"
            variant="translucent"
            size="28"
          />
          <span class="r-v2-audit__ellipsis">
            {{ actorName((row as Row).event) }}
          </span>
        </span>
      </template>
      <template #cell.what="{ row }">
        <span class="r-v2-audit__what">
          <RAvatar
            :icon="(row as Row).view.icon"
            variant="text"
            size="28"
            class="r-v2-audit__icon"
          />
          <span class="r-v2-audit__text">
            <component
              :is="(row as Row).view.to ? RouterLink : 'span'"
              :to="(row as Row).view.to ?? undefined"
              class="r-v2-audit__title"
            >
              {{ (row as Row).view.title }}
            </component>
            <span v-if="(row as Row).view.detail" class="r-v2-audit__detail">
              {{ (row as Row).view.detail }}
            </span>
          </span>
        </span>
      </template>
      <template #cell.device="{ row }">
        <span class="r-v2-audit__text">
          <span class="r-v2-audit__ellipsis">
            {{ (row as Row).event.device_name ?? "—" }}
          </span>
          <span
            v-if="(row as Row).event.ip_address"
            class="r-v2-audit__detail r-v2-audit__ip"
          >
            {{ (row as Row).event.ip_address }}
          </span>
        </span>
      </template>
    </RTable>

    <div v-if="hasMore" class="r-v2-audit__more">
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

.r-v2-audit__who,
.r-v2-audit__what {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.r-v2-audit__icon {
  flex-shrink: 0;
  color: var(--r-color-fg-muted);
}

.r-v2-audit__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.r-v2-audit__title {
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
}

a.r-v2-audit__title:hover {
  text-decoration: underline;
}

.r-v2-audit__detail {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-audit__ip {
  font-family: var(--r-font-family-mono);
}

.r-v2-audit__ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-audit__more {
  display: flex;
  justify-content: center;
}
</style>
