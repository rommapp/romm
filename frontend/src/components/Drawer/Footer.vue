<script setup>
import { inject } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";

import storeAuth from "@/stores/auth";

const props = defineProps(["rail"]);
const router = useRouter();
const emitter = inject("emitter");
const auth = storeAuth();

async function logout() {
  axios
    .post("/api/logout", {})
    .then(({ data }) => {
      emitter.emit("snackbarShow", {
        msg: data.message,
        icon: "mdi-close-circle",
        color: "green",
      });
      router.push("/login");
    })
    .catch(() => {
      router.push("/login");
    }).finally(() => {
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
      <v-avatar :class="{ 'ml-0': rail, 'my-2': rail }" >
        <v-img src="/assets/default_user.png" />
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
