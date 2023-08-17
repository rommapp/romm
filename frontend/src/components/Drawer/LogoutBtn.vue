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
  <v-list-item height="60" class="bg-primary text-button" rounded="0">
    {{ rail ? "" : "Zurdi" }}
    <template v-slot:prepend>
      <v-avatar :class="{ 'ml-4': rail, 'my-3': rail }">
        <v-img src="/assets/default_user.png" />
      </v-avatar>
    </template>
    <template v-slot:append>
      <v-btn v-if="!rail" variant="text" icon="mdi-location-exit" @click="logout()"></v-btn>
    </template>
  </v-list-item>
  <v-btn v-if="rail" variant="text" icon="mdi-location-exit" class="ml-7 my-1" @click="logout()"></v-btn>
</template>
