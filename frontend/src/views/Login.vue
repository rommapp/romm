<script setup>
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import Notification from "@/components/Notification.vue";

// Props
const emitter = inject("emitter");
const router = useRouter();
const username = ref();
const password = ref();
const visiblePassword = ref(false);
const validCredentials = ref(true);

// POC FOR VALIDATING AND TESTING LOGIN PAGE
async function login() {
  /* TODO: implement login logic */
  validCredentials.value = username.value == "zurdi";
  if (validCredentials.value) {
    localStorage.setItem("authenticated", true);
    await router.push({ name: "dashboard" }); // TODO: redirect to the last valid url
  } else {
    const msg = "Invalid credentials";
    emitter.emit("snackbarShow", {
      msg: `Unable to login: ${msg}`,
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}
// POC FOR VALIDATING AND TESTING LOGIN PAGE
</script>

<template>
  <span id="bg"></span>

  <notification class="mt-6" />

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
                rounded="0"
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
  background: url("/assets/login_bg.jpg") center center;
  background-size: cover;
}
#card {
  background-color: rgba(0, 0, 0, 0.3);
}
</style>
