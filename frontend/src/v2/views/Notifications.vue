<script setup lang="ts">
// Notifications: the user's inbox and the channels it's forwarded to, plus a
// tab an admin sends from. `?tab=` deep-links to either of the others.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storePermissions from "@/stores/permissions";
import NotificationChannelsSection from "@/v2/components/Notifications/NotificationChannelsSection.vue";
import NotificationInbox from "@/v2/components/Notifications/NotificationInbox.vue";
import SendNotificationSection from "@/v2/components/Notifications/SendNotificationSection.vue";
import { useCan } from "@/v2/composables/useCan";

type Tab = "inbox" | "channels" | "send";

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
  {
    id: "channels",
    label: t("notifications.channels"),
    icon: "mdi-send-variant-outline",
  },
  ...(isAdmin.value
    ? [
        {
          id: "send",
          label: t("notifications.send"),
          icon: "mdi-bullhorn-outline",
        },
      ]
    : []),
]);

// Null while permissions load: showing the inbox under a link to the form
// would mark everything read before the admin ever sees it.
const tab = computed<Tab | null>(() => {
  const asked = route.query.tab;
  if (asked === "channels") return "channels";
  if (asked !== "send") return "inbox";
  if (!permissions.hydrated) return null;
  return isAdmin.value ? "send" : "inbox";
});

const tabModel = computed<string>({
  get: () => tab.value ?? "send",
  set: (id) => {
    void router.replace({
      query: { ...route.query, tab: id === "inbox" ? undefined : id },
    });
  },
});
</script>

<template>
  <div class="r-v2-section-stack">
    <RTabNav v-model="tabModel" :items="tabs" />
    <SendNotificationSection v-if="tab === 'send'" />
    <NotificationChannelsSection v-else-if="tab === 'channels'" />
    <NotificationInbox v-else-if="tab === 'inbox'" />
  </div>
</template>
