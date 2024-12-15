<script setup lang="ts">
import Excluded from "@/components/Settings/LibraryManagement/Excluded.vue";
import PlatformBinding from "@/components/Settings/LibraryManagement/PlatformBinding.vue";
import PlatformVersions from "@/components/Settings/LibraryManagement/PlatformVersions.vue";
</script>

<template>
  <platform-binding />
  <platform-versions />
  <excluded />
</template>
