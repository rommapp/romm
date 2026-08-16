<script setup lang="ts">
// Administration — v2-native page chrome for the admin-only sections.
// Uses the shared `RTabNav` primitive (same one Library Management
// uses) to expose Users / Groups / Tasks / Streaming as sibling tabs,
// keeping the `?tab=` query param so deep links survive a reload.
//
// Tabs are gated by scope: `users.write` for the groups tab,
// `tasks.run` for the Tasks tab, `app.admin` for Streaming, whose every
// endpoint is admin-only. Users tab is always visible to anyone who can
// reach this route (route-level guard already checks `app.admin`).
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storeAuth from "@/stores/auth";
import CreateUserDialog from "@/v2/components/Settings/CreateUserDialog.vue";
import EditUserDialog from "@/v2/components/Settings/EditUserDialog.vue";
import GroupFormDialog from "@/v2/components/Settings/GroupFormDialog.vue";
import InviteLinkDialog from "@/v2/components/Settings/InviteLinkDialog.vue";
import PermissionGroupsSection from "@/v2/components/Settings/PermissionGroupsSection.vue";
import StreamingSection from "@/v2/components/Settings/StreamingSection.vue";
import TasksSection from "@/v2/components/Settings/TasksSection.vue";
import UsersSection from "@/v2/components/Settings/UsersSection.vue";
import { useCan } from "@/v2/composables/useCan";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = storeAuth();
const isAdmin = useCan("app.admin");

type Tab = "users" | "groups" | "tasks" | "streaming";
const validTabs: Tab[] = ["users", "groups", "tasks", "streaming"];

const tab = ref<Tab>(
  (validTabs as string[]).includes(route.query.tab as string)
    ? (route.query.tab as Tab)
    : "users",
);

watch(tab, (newTab) => {
  router.replace({
    path: route.path,
    query: { ...route.query, tab: newTab },
  });
});

watch(
  () => route.query.tab,
  (newTab) => {
    if (
      newTab &&
      (validTabs as string[]).includes(newTab as string) &&
      tab.value !== newTab
    ) {
      tab.value = newTab as Tab;
    }
  },
  { immediate: true },
);

const tabs = computed<RTabNavItem[]>(() => {
  const items: RTabNavItem[] = [
    {
      id: "users",
      label: t("settings.users"),
      icon: "mdi-account-group",
    },
  ];
  if (auth.scopes.includes("users.write")) {
    items.push({
      id: "groups",
      label: t("settings.permission-groups"),
      icon: "mdi-shield-lock-outline",
    });
  }
  if (auth.scopes.includes("tasks.run")) {
    items.push({
      id: "tasks",
      label: t("settings.tasks"),
      icon: "mdi-pulse",
    });
  }
  if (isAdmin.value) {
    items.push({
      id: "streaming",
      label: t("settings.streaming"),
      icon: "mdi-monitor-dashboard",
    });
  }
  return items;
});

// A tab nobody can see is not one the query param may select: the route
// admits `users.write` as well, and Streaming would otherwise deep-link them
// to a panel whose every request 403s.
watch(
  tabs,
  (items) => {
    if (!items.some((item) => item.id === tab.value)) tab.value = "users";
  },
  { immediate: true },
);

// Bridge between RTabNav's string modelValue and our Tab union.
const tabModel = computed<string>({
  get: () => tab.value,
  set: (v) => {
    if ((validTabs as string[]).includes(v)) tab.value = v as Tab;
  },
});
</script>

<template>
  <div class="r-v2-section-stack">
    <RTabNav v-model="tabModel" :items="tabs" />

    <UsersSection v-if="tab === 'users'" />
    <PermissionGroupsSection v-else-if="tab === 'groups'" />
    <TasksSection v-else-if="tab === 'tasks'" />
    <StreamingSection v-else-if="tab === 'streaming' && isAdmin" />

    <CreateUserDialog />
    <EditUserDialog />
    <InviteLinkDialog />
    <GroupFormDialog />
  </div>
</template>
