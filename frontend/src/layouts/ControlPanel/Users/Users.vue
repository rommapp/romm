<script setup lang="ts">
import UsersTable from "@/components/User/Table.vue";
import RSection from "@/components/common/Section.vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const userSearch = ref("");
</script>
<template>
  <r-section icon="mdi-account-group" title="Users">
    <template #toolbar-append>
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-romm-accent-1"
        @click="emitter?.emit('showCreateUserDialog', null)"
      >
        Add
      </v-btn>
    </template>
    <template #content>
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
      <users-table :user-search="userSearch" />
    </template>
  </r-section>
</template>
