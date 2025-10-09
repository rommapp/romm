<script setup lang="ts">
import { useActiveElement } from "@vueuse/core";
import type { Emitter } from "mitt";
import { getActivePinia, storeToRefs, type StateTree } from "pinia";
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import AboutDialog from "@/components/Settings/AboutDialog.vue";
import { ROUTES } from "@/plugins/router";
import { refetchCSRFToken } from "@/services/api";
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, getRoleIcon } from "@/utils";

const { t } = useI18n();
const navigationStore = storeNavigation();
const router = useRouter();
const auth = storeAuth();
const { user, scopes } = storeToRefs(auth);
const emitter = inject<Emitter<Events>>("emitter");
const { activeSettingsDrawer } = storeToRefs(navigationStore);
const { smAndDown, mdAndUp } = useDisplay();
const tabIndex = computed(() => (activeSettingsDrawer.value ? 0 : -1));
const activeElement = useActiveElement();

async function logout() {
  identityApi.logout().then(async () => {
    // Refetch CSRF token
    await refetchCSRFToken();

    emitter?.emit("snackbarShow", {
      msg: "Logged out successfully",
      icon: "mdi-check-bold",
      color: "green",
    });

    // Redirect to login page
    await router.push({ name: ROUTES.LOGIN });

    // Clear all pinia stores
    // @ts-expect-error(2339)
    getActivePinia()?._s.forEach((store: StateTree) => {
      store.reset?.();
    });
  });
}

const triggerElement = ref<HTMLElement | null | undefined>(undefined);
watch(activeSettingsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = activeElement.value;
  }
});

function onClose() {
  activeSettingsDrawer.value = false;
  // Refocus the trigger element for keyboard navigation
  triggerElement.value?.focus();
}
</script>
<template>
  <v-navigation-drawer
    v-model="activeSettingsDrawer"
    mobile
    :location="smAndDown ? 'top' : 'left'"
    :width="smAndDown ? 500 : 400"
    :class="{
      'my-2': mdAndUp || (smAndDown && activeSettingsDrawer),
      'ml-2': (mdAndUp && activeSettingsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
    }"
    class="bg-surface pa-1 unset-height"
    rounded
    :border="0"
    @keydown.esc="onClose"
  >
    <v-list tabindex="-1" class="pa-0">
      <v-list-img>
        <v-img
          :src="
            user?.avatar_path
              ? `/assets/romm/assets/${user?.avatar_path}?ts=${user?.updated_at}`
              : defaultAvatarPath
          "
          cover
          class="rounded"
        />
      </v-list-img>
      <v-list-item :title="user?.username" class="mb-1 text-shadow text-white">
        <template v-if="user?.role" #subtitle>
          <span class="mr-1">{{ user.role }}</span>
          <v-icon size="x-small">
            {{ getRoleIcon(user.role) }}
          </v-icon>
        </template>
      </v-list-item>
    </v-list>
    <v-list tabindex="-1" class="py-1 px-0">
      <v-list-item
        v-if="scopes.includes('me.write')"
        :tabindex="tabIndex"
        rounded
        :to="{ name: ROUTES.USER_PROFILE, params: { user: user?.id } }"
        append-icon="mdi-account"
        aria-label="Profile"
        role="listitem"
      >
        {{ t("common.profile") }}
      </v-list-item>
      <v-list-item
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.USER_INTERFACE }"
        append-icon="mdi-palette"
        aria-label="User Interface"
        role="listitem"
      >
        {{ t("common.user-interface") }}
      </v-list-item>
      <v-list-item
        v-if="scopes.includes('platforms.write')"
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        append-icon="mdi-table-cog"
        aria-label="Library management"
        role="listitem"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
      >
        {{ t("common.library-management") }}
      </v-list-item>
      <v-list-item
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        append-icon="mdi-database-cog"
        aria-label="Metadata sources"
        role="listitem"
        :to="{ name: ROUTES.METADATA_SOURCES }"
      >
        {{ t("scan.metadata-sources") }}
      </v-list-item>
      <v-list-item
        v-if="scopes.includes('users.write')"
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.ADMINISTRATION }"
        append-icon="mdi-security"
        aria-label="Administration"
        role="listitem"
      >
        {{ t("common.administration") }}
      </v-list-item>
      <v-list-item
        v-if="auth.user?.role === 'admin'"
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.SERVER_STATS }"
        append-icon="mdi-server"
        aria-label="Server Stats"
        role="listitem"
      >
        {{ t("common.server-stats") }}
      </v-list-item>
      <v-list-item
        v-if="auth.user?.role === 'admin'"
        :tabindex="tabIndex"
        class="mt-1"
        rounded
        append-icon="mdi-help-circle-outline"
        aria-label="About"
        role="listitem"
        @click="emitter?.emit('showAboutDialog', null)"
      >
        {{ t("common.about") }}
      </v-list-item>
    </v-list>
    <template v-if="scopes.includes('me.write')" #append>
      <v-btn
        :tabindex="tabIndex"
        append-icon="mdi-location-exit"
        block
        aria-label="Logout"
        class="bg-toplayer text-romm-red"
        @click="logout"
      >
        {{ t("common.logout") }}
      </v-btn>
    </template>
  </v-navigation-drawer>

  <AboutDialog />
</template>
