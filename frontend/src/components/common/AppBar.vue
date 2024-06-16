<script setup lang="ts">
import PlatformListItem from "@/components/Platform/ListItem.vue";
import RommIso from "@/components/common/RommIso.vue";
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const platforms = storePlatforms();
const auth = storeAuth();
const { mobile } = useDisplay();

// Functions
function toAdministration() {
  router.push({ name: "settingsUsers" });
}

function toConfig() {
  router.push({ name: "settingsGeneral" });
}

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
  <v-app-bar elevation="0" density="compact">
    <template #prepend>
      <router-link :to="{ name: 'dashboard' }">
        <romm-iso class="ml-5" :size="35" />
      </router-link>
      <v-btn
        v-if="mobile"
        rounded="0"
        class="ml-2"
        icon="mdi-menu"
        @click="emitter?.emit('toggleDrawer', null)"
      />
    </template>
    <template #default>
      <v-row no-gutters class="text-center">
        <v-col>
          <!-- Platforms -->
          <v-menu
            v-if="!mobile"
            :width="mobile ? '90vw' : 400"
            max-height="650"
            open-delay="0"
            close-delay="0"
            :open-on-hover="!mobile"
            transition="slide-y-transition"
          >
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                size="x-large"
                rounded="0"
                class="ml-5"
                prepend-icon="mdi-controller"
                append-icon="mdi-chevron-down"
              >
                <span class="text-button">Platforms</span>
              </v-btn>
            </template>
            <v-list rounded="0" class="pa-0">
              <platform-list-item
                v-for="platform in platforms.filledPlatforms"
                :key="platform.slug"
                :platform="platform"
                class="py-4"
              />
            </v-list>
          </v-menu>

          <!-- Library -->
          <v-menu
            v-if="!mobile"
            open-delay="0"
            close-delay="0"
            :open-on-hover="!mobile"
            transition="slide-y-transition"
          >
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                size="x-large"
                rounded="0"
                class="ml-5"
                prepend-icon="mdi-animation-outline"
                append-icon="mdi-chevron-down"
              >
                <span class="text-button">Library</span>
              </v-btn>
            </template>
            <v-list rounded="0" class="bg-terciary pa-0">
              <v-list-item
                append-icon="mdi-magnify-scan"
                :to="{ name: 'libraryScan' }"
              >
                Scan
              </v-list-item>
              <v-list-item
                v-if="auth.scopes.includes('platforms.write')"
                append-icon="mdi-table-cog"
                :to="{ name: 'libraryConfig' }"
                >Configuration
              </v-list-item>
            </v-list>
          </v-menu>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-btn
        size="small"
        class="mr-2"
        icon="mdi-upload"
        @click="emitter?.emit('showUploadRomDialog', null)"
      />
      <v-btn
        size="small"
        icon="mdi-magnify"
        class="mr-2"
        @click="emitter?.emit('showSearchRomDialog', null)"
      />
      <v-menu
        open-delay="0"
        close-delay="0"
        offset="4"
        transition="slide-y-transition"
      >
        <template #activator="{ props }">
          <v-avatar v-bind="props" class="mr-2 pointer" size="40">
            <v-img
              :src="
                auth.user?.avatar_path
                  ? `/assets/romm/assets/${auth.user?.avatar_path}`
                  : defaultAvatarPath
              "
            />
          </v-avatar>
        </template>
        <v-list rounded="0" class="bg-terciary pa-0">
          <v-list-item @click="toConfig" append-icon="mdi-cog"
            >Configuration</v-list-item
          >
          <v-list-item @click="toAdministration" append-icon="mdi-security"
            >Administration</v-list-item
          >
          <v-list-item @click="logout" append-icon="mdi-location-exit"
            >Logout</v-list-item
          >
        </v-list>
      </v-menu>
    </template>
  </v-app-bar>
</template>
