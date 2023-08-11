<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const visible = ref(false);

async function login() {
  /* TODO: implement login logic */
  localStorage.setItem("authenticated", true);
  await router.push({ name: "dashboard" });
}
</script>

<template>
  <span class="bg"></span>

  <v-container class="fill-height">
    <v-row>
      <v-col>
        <v-row no-gutters>
          <v-img src="/assets/isotipo.svg" id="login-logo" />
        </v-row>

        <v-row class="justify-center mt-7" no-gutters>
          <v-col cols="6" xs="6" sm="5" md="4" lg="3">
            <v-text-field
              @keyup.enter="login()"
              prepend-inner-icon="mdi-account"
              type="text"
              label="Username"
              variant="underlined"
            ></v-text-field>
            <v-text-field
              @keyup.enter="login()"
              prepend-inner-icon="mdi-lock"
              :type="visible ? 'text' : 'password'"
              label="Password"
              variant="underlined"
              :append-inner-icon="visible ? 'mdi-eye-off' : 'mdi-eye'"
              @click:append-inner="visible = !visible"
            ></v-text-field>
          </v-col>
        </v-row>

        <v-row class="justify-center mt-7" no-gutters>
          <v-btn
            @click="login()"
            rounded="0"
            class="bg-primary"
            append-icon="mdi-chevron-right-circle-outline"
            >Sign In</v-btn
          >
        </v-row>
      </v-col>
    </v-row>
  </v-container>
</template>

<style>
.bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.jpg") no-repeat center center;
  background-size: cover;
  transform: scale(1);
  /* -webkit-filter: blur(4px);
  filter: blur(4px); */
}
#login-logo {
  width: 200px;
  height: 200px;
}
</style>
