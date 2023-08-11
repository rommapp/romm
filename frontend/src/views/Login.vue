<script setup>
import { inject, onMounted } from "vue";
import { useRouter } from "vue-router";

const emitter = inject("emitter");
const router = useRouter();

async function login() {
  /* TODO: implement login logic */
  localStorage.setItem("login", true);
  emitter.emit("login", true);
  await router.push("/");
}
</script>

<template>
  <span class="bg"></span>
  <v-row class="pa-2" no-gutters>
    <v-img src="/assets/isotipo.svg" class="login-logo ma-16" />
  </v-row>
  <v-row class="pa-2" no-gutters>
    <v-spacer />
    <v-col cols="12" xs="12" sm="10" md="10" lg="2">
      <v-text-field
        @keyup.enter="login()"
        type="text"
        label="username"
        variant="underlined"
      ></v-text-field>
      <v-text-field
        @keyup.enter="login()"
        type="password"
        label="password"
        variant="underlined"
      ></v-text-field>
    </v-col>
    <v-spacer />
  </v-row>

  <v-row class="justify-center" no-gutters>
    <v-btn @click="login()" rounded="0" class="bg-terciary" >Login</v-btn>
  </v-row>
</template>

<style>
.login-logo {
  width: 300px;
  height: 300px;
}
.bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.jpg") no-repeat center center;
  background-size: cover;
  transform: scale(1);
  /* -webkit-filter: blur(3px);
  filter: blur(3px); */
}
</style>
