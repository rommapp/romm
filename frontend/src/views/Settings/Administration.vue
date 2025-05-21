<script setup lang="ts">
import UsersTable from "@/components/Settings/Administration/Users/Table.vue";
import Tasks from "@/components/Settings/Administration/Tasks.vue";
import storeAuth from "@/stores/auth";

// Props
const auth = storeAuth();
</script>
<template>
  <users-table />
  <tasks class="mt-6" v-if="auth.scopes.includes('tasks.run')" />
</template>
