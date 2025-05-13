<script setup lang="ts">
import type { UserSchema } from "@/__generated__";
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, getRoleIcon } from "@/utils";
import { ROUTES } from "@/plugins/router";
import type { Emitter } from "mitt";
import { storeToRefs, getActivePinia, type StateTree } from "pinia";
import { inject, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const router = useRouter();
const auth = storeAuth();
const { user, scopes } = storeToRefs(auth);
const emitter = inject<Emitter<Events>>("emitter");
const { activeSettingsDrawer } = storeToRefs(navigationStore);
const { smAndDown, mdAndUp } = useDisplay();

// Functions
async function logout() {
  identityApi.logout().then(async ({ data }) => {
    // Refetch CSRF token
    await refetchCSRFToken();

    emitter?.emit("snackbarShow", {
      msg: data.msg,
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

// Ref to store the element that triggered the drawer
const triggerElement = ref<HTMLElement | null>(null);
// Watch for changes in the navigation drawer state
const firstElementRef = ref();
watch(activeSettingsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = document.activeElement as HTMLElement;
    // Focus the first element when the drawer is opened
    firstElementRef.value?.focus();
  }
});

// Close the drawer when the Esc key is pressed
function handleDrawerCloseOnEsc(event: KeyboardEvent) {
  if (event.key === "Escape") {
    activeSettingsDrawer.value = false;
    // Focus the element that triggered the drawer
    triggerElement.value?.focus();
  }
}
</script>
<template>
  <v-navigation-drawer
    mobile
    :location="smAndDown ? 'top' : 'left'"
    width="450"
    v-model="activeSettingsDrawer"
    :class="{
      'my-2': mdAndUp || (smAndDown && activeSettingsDrawer),
      'ml-2': (mdAndUp && activeSettingsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
    }"
    class="bg-surface pa-1 unset-height"
    rounded
    :border="0"
    @keydown="handleDrawerCloseOnEsc"
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
        >
        </v-img>
      </v-list-img>
      <v-list-item :title="user?.username" class="mb-1 text-shadow text-white">
        <template #subtitle>
          <v-list-item-subtitle v-if="user?.role">
            {{ user.role }}
            <v-icon size="x-small">{{ getRoleIcon(user.role) }}</v-icon>
          </v-list-item-subtitle>
        </template>
      </v-list-item>
    </v-list>
    <v-list class="py-1 px-0">
      <v-list-item
        v-if="scopes.includes('me.write')"
        ref="firstElementRef"
        :tabindex="activeSettingsDrawer ? 0 : -1"
        rounded
        :to="{ name: ROUTES.USER_PROFILE, params: { user: user?.id } }"
        append-icon="mdi-account"
        >{{ t("common.profile") }}</v-list-item
      >
      <v-list-item
        :tabindex="activeSettingsDrawer ? 0 : -1"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.USER_INTERFACE }"
        append-icon="mdi-palette"
        >{{ t("common.user-interface") }}</v-list-item
      >
      <v-list-item
        v-if="scopes.includes('platforms.write')"
        :tabindex="activeSettingsDrawer ? 0 : -1"
        class="mt-1"
        rounded
        append-icon="mdi-table-cog"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
        >{{ t("common.library-management") }}
      </v-list-item>
      <v-list-item
        v-if="scopes.includes('users.write')"
        :tabindex="activeSettingsDrawer ? 0 : -1"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.ADMINISTRATION }"
        append-icon="mdi-security"
        >{{ t("common.administration") }}
      </v-list-item>
    </v-list>
    <template v-if="scopes.includes('me.write')" #append>
      <v-btn
        @click="logout"
        :tabindex="activeSettingsDrawer ? 0 : -1"
        append-icon="mdi-location-exit"
        block
        class="bg-toplayer text-romm-red"
        >{{ t("common.logout") }}</v-btn
      >
    </template>
  </v-navigation-drawer>
</template>
