<script setup lang="ts">
// Logs: for admins, the event log of what users did, and the live backend
// log. `?tab=logs` deep-links to the second.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import EventLog from "@/v2/components/Settings/EventLog.vue";
import LogViewer from "@/v2/components/Settings/LogViewer.vue";
import { useCan } from "@/v2/composables/useCan";

type Tab = "logs" | "events";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { scopes } = storeToRefs(storeAuth());
const heartbeat = storeHeartbeat();
const isAdmin = useCan("app.admin");

const canSeeLogs = computed(
  () =>
    !heartbeat.value.FRONTEND.DISABLE_LOGS_VIEWER &&
    scopes.value.includes("logs.read"),
);

const tabs = computed<RTabNavItem[]>(() => [
  ...(isAdmin.value
    ? [
        {
          id: "events",
          label: t("audit.events"),
          icon: "mdi-timeline-clock-outline",
        },
      ]
    : []),
  ...(canSeeLogs.value
    ? [
        {
          id: "logs",
          label: t("common.logs"),
          icon: "mdi-text-box-search-outline",
        },
      ]
    : []),
]);

const tab = computed<Tab | null>(() => {
  const available = tabs.value.map((item) => item.id as Tab);
  const asked = route.query.tab === "logs" ? "logs" : "events";
  return available.includes(asked) ? asked : (available[0] ?? null);
});

const tabModel = computed<string>({
  get: () => tab.value ?? "events",
  set: (id) => {
    // Each tab owns the rest of the query, so switching starts it clean.
    void router.replace({ query: id === "logs" ? { tab: id } : {} });
  },
});
</script>

<template>
  <div class="r-v2-logs-page">
    <RTabNav v-if="tabs.length > 1" v-model="tabModel" :items="tabs" />
    <div class="r-v2-logs-page__body">
      <EventLog v-if="tab === 'events'" />
      <LogViewer v-else-if="tab === 'logs'" />
    </div>
  </div>
</template>

<style scoped>
/* The route pins the page to the viewport; each tab scrolls inside it. */
.r-v2-logs-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.r-v2-logs-page__body {
  flex: 1;
  min-height: 0;
}
</style>
