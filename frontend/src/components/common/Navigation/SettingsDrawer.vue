<script setup lang="ts">
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const navigationStore = storeNavigation();
const router = useRouter();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const { activeSettingsDrawer } = storeToRefs(navigationStore);
const { smAndDown } = useDisplay();

// Functions
async function logout() {
  identityApi
    .logout()
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      router.push({ name: "login" });
    })
    .catch(() => {
      router.push({ name: "login" });
    })
    .finally(() => {
      auth.setUser(null);
    });
}
</script>
<template>
  <v-navigation-drawer
    :location="smAndDown ? 'top' : 'left'"
    mobile
    width="300"
    v-model="activeSettingsDrawer"
    class="bg-terciary"
  >
    <v-list rounded="0" class="pa-0">
      <v-list-img>
        <v-img
          :src="
            auth.user?.avatar_path
              ? `/assets/romm/assets/${auth.user?.avatar_path}?ts=${auth.user?.updated_at}`
              : defaultAvatarPath
          "
          cover
        >
        </v-img>
      </v-list-img>
      <v-list-item class="mb-1 text-shadow text-white">
        <template #title>
          <span>{{ auth.user?.username }}</span>
        </template>
        <template #subtitle>
          <span>{{ auth.user?.role }}</span>
        </template>
      </v-list-item>
    </v-list>
    <v-list rounded="0" class="pa-0">
      <v-list-item :to="{ name: 'settings' }" append-icon="mdi-palette"
        >UI Settings</v-list-item
      >
      <v-list-item
        v-if="auth.scopes.includes('platforms.write')"
        append-icon="mdi-table-cog"
        :to="{ name: 'management' }"
        >Library Management
      </v-list-item>
      <v-list-item
        v-if="auth.scopes.includes('users.write')"
        :to="{ name: 'administration' }"
        append-icon="mdi-security"
        >Administration</v-list-item
      >
      <template v-if="smAndDown">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit"
          >Logout</v-list-item
        >
      </template>
    </v-list>
    <template v-if="!smAndDown" #append>
      <v-list rounded="0" class="pa-0">
        <v-divider />
        <v-list-item @click="logout" append-icon="mdi-location-exit"
          >Logout</v-list-item
        >
      </v-list>
    </template>
  </v-navigation-drawer>
</template>
