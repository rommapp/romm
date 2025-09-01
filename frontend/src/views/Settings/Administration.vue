<script setup lang="ts">
import Tasks from "@/components/Settings/Administration/Tasks.vue";
import UsersTable from "@/components/Settings/Administration/Users/Table.vue";
import storeAuth from "@/stores/auth";

const auth = storeAuth();
</script>
<template>
  <users-table />
  <tasks class="mt-6" v-if="auth.scopes.includes('tasks.run')" />
</template>
