<script setup lang="ts">
import type { UserSchema } from "@/__generated__";
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
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
const { smAndDown } = useDisplay();

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
    navigationStore.switchActiveSettingsDrawer();
  });

  await router.push({ name: "login" });
  auth.setUser(null);
}
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="500"
    v-model="activeSettingsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <v-list-img>
        <v-img
          :src="
            user?.avatar_path
              ? `/assets/romm/assets/${user?.avatar_path}?ts=${user?.updated_at}`
              : defaultAvatarPath
          "
          cover
        >
        </v-img>
      </v-list-img>
      <v-list-item
        :title="user?.username"
        :subtitle="user?.role"
        class="mb-1 text-shadow text-white"
      >
      </v-list-item>
    </v-list>
    <v-list rounded="0" class="pa-0">
      <v-list-item
        @click="emitter?.emit('showEditUserDialog', auth.user as UserSchema)"
        append-icon="mdi-account"
        >{{ t("common.profile") }}</v-list-item
      >
      <v-list-item :to="{ name: 'userInterface' }" append-icon="mdi-palette">{{
        t("common.user-interface")
      }}</v-list-item>
      <v-list-item
        v-if="scopes.includes('platforms.write')"
        append-icon="mdi-table-cog"
        :to="{ name: 'libraryManagement' }"
        >{{ t("common.library-management") }}
      </v-list-item>
      <v-list-item
        v-if="scopes.includes('users.write')"
        :to="{ name: 'administration' }"
        append-icon="mdi-security"
        >{{ t("common.administration") }}</v-list-item
      >
      <template v-if="smAndDown">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit">{{
          t("common.logout")
        }}</v-list-item>
      </template>
    </v-list>
    <template v-if="!smAndDown" #append>
      <v-list rounded="0" class="pa-0">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit">{{
          t("common.logout")
        }}</v-list-item>
      </v-list>
    </template>
  </v-navigation-drawer>
</template>
