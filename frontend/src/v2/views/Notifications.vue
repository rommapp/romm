<script setup lang="ts">
// Notifications: the user's inbox, beside which an admin gets a tab to send
// one. `?tab=send` deep-links to it.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storePermissions from "@/stores/permissions";
import NotificationInbox from "@/v2/components/Notifications/NotificationInbox.vue";
import SendNotificationSection from "@/v2/components/Notifications/SendNotificationSection.vue";
import { useCan } from "@/v2/composables/useCan";

type Tab = "inbox" | "send";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const permissions = storePermissions();
const isAdmin = useCan("app.admin");

const tabs = computed<RTabNavItem[]>(() => [
  {
    id: "inbox",
    label: t("notifications.notifications"),
    icon: "mdi-bell-outline",
  },
  { id: "send", label: t("notifications.send"), icon: "mdi-bullhorn-outline" },
]);

// Null while permissions load: showing the inbox under a link to the form
// would mark everything read before the admin ever sees it.
const tab = computed<Tab | null>(() => {
  if (route.query.tab !== "send") return "inbox";
  if (!permissions.hydrated) return null;
  return isAdmin.value ? "send" : "inbox";
});

const tabModel = computed<string>({
  get: () => tab.value ?? "send",
  set: (id) => {
    void router.replace({
      query: { ...route.query, tab: id === "send" ? "send" : undefined },
    });
  },
});
</script>

<template>
  <div class="r-v2-section-stack">
    <RTabNav v-if="isAdmin" v-model="tabModel" :items="tabs" />
    <SendNotificationSection v-if="tab === 'send'" />
    <NotificationInbox v-else-if="tab === 'inbox'" />
  </div>
</template>
