<script setup>
import { useRouter } from "vue-router";

const props = defineProps(["rail"]);
const router = useRouter();

async function logout() {
  /* TODO: implement logout logic */
  localStorage.setItem("authenticated", false);
  await router.push({ name: "login" });
}
</script>

<template>
  <v-btn
    class="drawer-item"
    @click="logout()"
    rounded="0"
    color="primary"
    block
  >
    {{ rail ? "" : "Logout" }}
    <v-icon :class="{'ml-3': !rail}">mdi-logout-variant</v-icon>
  </v-btn>
</template>
