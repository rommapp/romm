<script setup>
const props = defineProps(["rom"]);
</script>
<template>
  <v-list rounded="0" class="pa-0">
    <v-list-item v-for="save in rom.saves">
      <v-list-item-title>
        {{ save.file_name }}
      </v-list-item-title>
    </v-list-item>
  </v-list>
</template>
