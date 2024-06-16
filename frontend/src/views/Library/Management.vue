<script setup lang="ts">
import Excluded from "@/layouts/Library/Configuration/Excluded.vue";
import PlatformBinding from "@/layouts/Library/Configuration/PlatformBinding.vue";
import PlatformVersions from "@/layouts/Library/Configuration/PlatformVersions.vue";
</script>

<template>
  <platform-binding />
  <platform-versions />
  <excluded />
</template>
