<script setup lang="ts">
import Tasks from "@/components/Settings/Administration/Tasks.vue";
import TokensTable from "@/components/Settings/Administration/Tokens/TokensTable.vue";
import UsersTable from "@/components/Settings/Administration/Users/UsersTable.vue";
import storeAuth from "@/stores/auth";

const auth = storeAuth();
</script>
<template>
  <UsersTable />
  <TokensTable v-if="auth.scopes.includes('users.read')" class="mt-6" />
  <Tasks v-if="auth.scopes.includes('tasks.run')" class="mt-6" />
</template>
