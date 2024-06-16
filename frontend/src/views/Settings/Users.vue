<script setup lang="ts">
import UsersTable from "@/components/User/Table.vue";
import { ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const userSearch = ref("");
const { mdAndDown } = useDisplay();
</script>
<template>
  <v-text-field
    v-model="userSearch"
    prepend-inner-icon="mdi-magnify"
    label="Search"
    rounded="0"
    single-line
    hide-details
    clearable
    density="comfortable"
    class="bg-secondary"
  />
  <users-table class="fill-height" :user-search="userSearch" />
</template>
