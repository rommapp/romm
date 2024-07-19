<script setup lang="ts">
import DeleteBtn from "@/components/Gallery/AppBar/Collection/DeleteBtn.vue";
import EditBtn from "@/components/Gallery/AppBar/Collection/EditBtn.vue";
</script>

<template>
  <v-list rounded="0" class="pa-0">
    <edit-btn />
    <v-divider />
    <delete-btn />
  </v-list>
</template>
