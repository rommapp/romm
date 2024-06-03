<script setup lang="ts">
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, ref } from "vue";
import { useRouter } from "vue-router";

// Props
defineProps<{ rail?: boolean }>();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const heartbeat = storeHeartbeat();
const { VERSION } = heartbeat.value;
const GITHUB_VERSION = ref(VERSION);
const latestVersionDismissed = ref(VERSION === "development");

function dismissVersionBanner() {
  localStorage.setItem("dismissedVersion", GITHUB_VERSION.value);
  latestVersionDismissed.value = true;
}

onBeforeMount(async () => {
  const response = await fetch(
    "https://api.github.com/repos/rommapp/romm/releases/latest"
  );
  const json = await response.json();
  GITHUB_VERSION.value = json.tag_name;
  latestVersionDismissed.value =
    VERSION === "development" ||
    json.tag_name === localStorage.getItem("dismissedVersion");
});

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
  <v-list-item
    height="60"
    class="bg-primary text-button"
    rounded="0"
  >
    <template v-if="!rail">
      <div class="text-no-wrap text-truncate text-subtitle-1">
        {{ auth.user?.username }}
      </div>
      <div class="text-no-wrap text-truncate text-caption text-romm-accent-1">
        {{ auth.user?.role }}
      </div>
    </template>
    <template #prepend>
      <v-avatar size="40">
        <v-img
          :src="
            auth.user?.avatar_path
              ? `/assets/romm/assets/${auth.user?.avatar_path}`
              : defaultAvatarPath
          "
        />
      </v-avatar>
    </template>
    <template #append>
      <v-btn
        v-if="!rail"
        variant="text"
        icon="mdi-location-exit"
        @click="logout()"
      />
    </template>
  </v-list-item>
  <v-btn
    v-if="rail"
    rounded="0"
    variant="text"
    icon="mdi-location-exit"
    block
    @click="logout()"
  />
  <v-list-item
    v-if="
      GITHUB_VERSION &&
      VERSION < GITHUB_VERSION &&
      !latestVersionDismissed &&
      !rail
    "
    class="bg-terciary py-1 px-1 text-subtitle-2"
  >
    <v-card>
      <v-card-text class="py-2 px-4">
        <v-row no-gutters>
          <v-col class="py-1">
            <span
              >New version available
              <span class="text-romm-accent-1"
                >v{{ GITHUB_VERSION }}</span
              ></span
            >
          </v-col>
        </v-row>
        <v-row no-gutters>
          <v-col class="py-1">
            <span class="pointer text-grey" @click="dismissVersionBanner"
              >Dismiss</span
            ><span class="ml-4"
              ><a
                target="_blank"
                :href="`https://github.com/rommapp/romm/releases/tag/${GITHUB_VERSION}`"
                >See what's new!</a
              ></span
            >
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-list-item>
</template>
