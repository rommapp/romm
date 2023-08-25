<script setup>
import { inject } from "vue";
import { useRouter } from "vue-router";
import storeAuth from "@/stores/auth";
import { defaultAvatarPath } from "@/utils/utils"
import { api } from "@/services/api";

// Props
const props = defineProps(["rail"]);
const router = useRouter();
const emitter = inject("emitter");
const auth = storeAuth();

// Functions
async function logout() {
  api
    .post("/logout", {})
    .then(({ data }) => {
      emitter.emit("snackbarShow", {
        msg: data.message,
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
      <div class="text-no-wrap text-truncate text-subtitle-1">{{ auth.user?.username }}</div>
      <div class="text-no-wrap text-truncate text-caption">{{ auth.user?.role }}</div>
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
</template>
