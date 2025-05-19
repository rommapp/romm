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
import { inject } from "vue";
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
  >
    <v-list class="pa-0">
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
        rounded
        :to="{ name: ROUTES.USER_PROFILE, params: { user: user?.id } }"
        append-icon="mdi-account"
        >{{ t("common.profile") }}</v-list-item
      >
      <v-list-item
        class="mt-1"
        rounded
        :to="{ name: ROUTES.USER_INTERFACE }"
        append-icon="mdi-palette"
        >{{ t("common.user-interface") }}</v-list-item
      >
      <v-list-item
        v-if="scopes.includes('platforms.write')"
        class="mt-1"
        rounded
        append-icon="mdi-table-cog"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
        >{{ t("common.library-management") }}
      </v-list-item>
      <v-list-item
        v-if="scopes.includes('users.write')"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.ADMINISTRATION }"
        append-icon="mdi-security"
        >{{ t("common.administration") }}
      </v-list-item>
      <v-list-item
        v-if="auth.user?.role === 'admin'"
        class="mt-1"
        rounded
        :to="{ name: ROUTES.SERVER_STATS }"
        append-icon="mdi-server"
        >{{ t("common.server-stats") }}
      </v-list-item>
    </v-list>
    <template v-if="scopes.includes('me.write')" #append>
      <v-btn
        @click="logout"
        append-icon="mdi-location-exit"
        block
        class="bg-toplayer text-romm-red"
        >{{ t("common.logout") }}</v-btn
      >
    </template>
  </v-navigation-drawer>
</template>
