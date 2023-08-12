<script setup>
const props = defineProps(["rail"]);
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
    <v-icon class="ml-3">mdi-logout-variant</v-icon>
  </v-btn>
</template>
