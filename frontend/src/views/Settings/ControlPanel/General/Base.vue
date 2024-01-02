<script setup lang="ts">
import Theme from "@/components/Settings/General/Theme/ThemeCard.vue";
import InterfaceOptions from "@/components/Settings/General/Interface/InterfaceOptions.vue";
import TaskStatus from "@/components/Settings/General/TaskStatus/TaskStatusCard.vue";
</script>

<template>
  <theme />
  <interface-options class="mt-1" />
  <task-status class="mt-1" />
</template>
