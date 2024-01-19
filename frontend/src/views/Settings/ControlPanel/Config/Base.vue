<script setup lang="ts">
import ExclusionsCard from "@/components/Settings/Config/ExclusionsCard.vue";
import PlatformBinding from "@/components/Settings/Config/PlatformBindingCard.vue";
import PlatformVersions from "@/components/Settings/Config/PlatformVersionsCard.vue";
</script>

<template>
  <platform-binding />
  <platform-versions />
  <exclusions-card class="mt-1" />
</template>
