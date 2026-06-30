<script setup lang="ts">
// Administration — v2-native page chrome for the admin-only sections.
// Uses the shared `RTabNav` primitive (same one Library Management
// uses) to expose Users / API tokens / Tasks as sibling tabs, keeping
// the `?tab=` query param so deep links survive a reload.
//
// Tabs are gated by scope: `users.read` for the admin tokens tab,
// `tasks.run` for the Tasks tab. Users tab is always visible to anyone
// who can reach this route (route-level guard already checks
// `app.admin`).
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storeAuth from "@/stores/auth";
import AdminTokensSection from "@/v2/components/Settings/AdminTokensSection.vue";
import CreateUserDialog from "@/v2/components/Settings/CreateUserDialog.vue";
import EditUserDialog from "@/v2/components/Settings/EditUserDialog.vue";
import GroupFormDialog from "@/v2/components/Settings/GroupFormDialog.vue";
import InviteLinkDialog from "@/v2/components/Settings/InviteLinkDialog.vue";
import PermissionGroupsSection from "@/v2/components/Settings/PermissionGroupsSection.vue";
import TasksSection from "@/v2/components/Settings/TasksSection.vue";
import UsersSection from "@/v2/components/Settings/UsersSection.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = storeAuth();

type Tab = "users" | "groups" | "tokens" | "tasks";
const validTabs: Tab[] = ["users", "groups", "tokens", "tasks"];

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
  if (auth.scopes.includes("users.read")) {
    items.push({
      id: "tokens",
      label: t("settings.client-api-tokens"),
      icon: "mdi-key-variant",
    });
  }
  if (auth.scopes.includes("tasks.run")) {
    items.push({
      id: "tasks",
      label: t("settings.tasks"),
      icon: "mdi-pulse",
    });
  }
  return items;
});

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
    <AdminTokensSection v-else-if="tab === 'tokens'" />
    <TasksSection v-else-if="tab === 'tasks'" />

    <CreateUserDialog />
    <EditUserDialog />
    <InviteLinkDialog />
    <GroupFormDialog />
  </div>
</template>
