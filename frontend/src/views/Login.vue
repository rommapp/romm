<script setup>
import { ref, inject, onBeforeMount } from "vue";
import { useRouter } from "vue-router";
import storeAuth from "@/stores/auth";
import { api } from "@/services/api";

// Props
const auth = storeAuth();
const emitter = inject("emitter");
const router = useRouter();
const username = ref();
const password = ref();
const visiblePassword = ref(false);

function login() {
  api
    .post(
      "/login",
      {},
      {
        auth: {
          username: username.value,
          password: password.value,
        },
      }
    )
    .then(() => {
      const next = router.currentRoute.value.query?.next || "/";
      router.push(next);
    })
    .catch(({ response, message }) => {
      emitter.emit("snackbarShow", {
        msg: `Unable to login: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
}

onBeforeMount(async () => {
  // Check if authentication is enabled
  if (!auth.enabled) {
    return router.push("/");
  }
});
</script>

<template>
  <span id="bg"></span>

  <v-container class="fill-height justify-center">
    <v-card id="card" class="py-8 px-5" width="500">
      <v-row>
        <v-col>
          <v-img
            src="/assets/isotipo.svg"
            class="mx-auto"
            width="200"
            height="200"
          />

          <v-row class="justify-center">
            <v-col cols="10" md="8">
              <v-text-field
                @keyup.enter="login()"
                prepend-inner-icon="mdi-account"
                type="text"
                v-model="username"
                label="Username"
                variant="underlined"
              ></v-text-field>
              <v-text-field
                @keyup.enter="login()"
                prepend-inner-icon="mdi-lock"
                :type="visiblePassword ? 'text' : 'password'"
                v-model="password"
                label="Password"
                variant="underlined"
                :append-inner-icon="visiblePassword ? 'mdi-eye-off' : 'mdi-eye'"
                @click:append-inner="visiblePassword = !visiblePassword"
              ></v-text-field>
            </v-col>
          </v-row>

          <v-row class="justify-center">
            <v-col cols="10" md="8">
              <v-btn
                @click="login()"
                append-icon="mdi-chevron-right-circle-outline"
                block
                >Login</v-btn
              >
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </v-card>
  </v-container>
</template>

<style>
#bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.png") center center;
  background-size: cover;
  -webkit-filter: blur(3px);
  filter: blur(3px);
}
#card {
  background-color: rgba(0, 0, 0, 0.4);
}
</style>
