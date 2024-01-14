<script setup lang="ts">
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import { defaultAvatarPath } from "@/utils";
import { api } from "@/services/api";

// Props
defineProps<{ rail?: boolean }>();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const heartbeat = storeHeartbeat();
const newVersion = heartbeat.value.NEW_VERSION;
localStorage.setItem("newVersion", newVersion)
const newVersionDismissed = ref(localStorage.getItem("dismissNewVersion") === newVersion);

// Functions
function dismissNewVersion() {
  localStorage.setItem("dismissNewVersion", newVersion);
  newVersionDismissed.value = true;
}

async function logout() {
  api
    .post("/logout", {})
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      router.push("/login");
    })
    .catch(() => {
      router.push("/login");
    })
    .finally(() => {
      auth.setUser(null);
    });
}
</script>

<template>
  <v-list-item height="60" class="bg-primary text-button" rounded="0">
    <template v-if="!rail">
      <div class="text-no-wrap text-truncate text-subtitle-1">
        {{ auth.user?.username }}
      </div>
      <div class="text-no-wrap text-truncate text-caption text-romm-accent-1">
        {{ auth.user?.role }}
      </div>
    </template>
    <template v-slot:prepend>
      <v-avatar :class="{ 'my-2': rail }">
        <v-img
          :src="
            auth.user?.avatar_path
              ? `/assets/romm/resources/${auth.user?.avatar_path}`
              : defaultAvatarPath
          "
        />
      </v-avatar>
    </template>
    <template v-slot:append>
      <v-btn
        v-if="!rail"
        variant="text"
        icon="mdi-location-exit"
        @click="logout()"
      ></v-btn>
    </template>
  </v-list-item>
  <v-btn
    v-if="rail"
    rounded="0"
    variant="text"
    icon="mdi-location-exit"
    block
    @click="logout()"
  ></v-btn>
  <v-list-item
    class="bg-terciary py-1 px-1 text-subtitle-2"
    v-if="newVersion && !newVersionDismissed && !rail"
  >
    <v-card>
      <v-card-text class="py-2 px-4">
        <v-row no-gutters>
          <v-col class="py-1">
            <span
              >New version available <span class="text-romm-accent-1">{{ newVersion }}</span></span
            >
          </v-col>
        </v-row>
        <v-row no-gutters>
          <v-col class="py-1">
            <span @click="dismissNewVersion()" class="pointer text-grey">Dismiss</span><span class="ml-4"><a target="_blank" :href="`https://github.com/zurdi15/romm/releases/tag/v${newVersion}`">See what's new!</a></span>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-list-item>
</template>
<style scoped>
.pointer {
  cursor: pointer;
}
</style>