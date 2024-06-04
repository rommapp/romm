<script setup lang="ts">
import RTable from "@/components/User/Table.vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const userSearch = ref("");
</script>
<template>
  <v-card rounded="0" elevation="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3"> mdi-account-group </v-icon>Users
      </v-toolbar-title>
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter?.emit('showCreateUserDialog', null)"
      >
        Add
      </v-btn>
    </v-toolbar>

    <v-divider />

    <v-card-text class="pa-0">
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
      <r-table :user-search="userSearch" />
    </v-card-text>
  </v-card>
</template>
