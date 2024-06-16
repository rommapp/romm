<script setup lang="ts">
import UsersTable from "@/components/User/Table.vue";
import Tasks from "@/layouts/Settings/General/Tasks.vue";
import storeAuth from "@/stores/auth";

// Props
const auth = storeAuth();
</script>
<template>
  <users-table  />
  <tasks v-if="auth.scopes.includes('tasks.run')" />
</template>
