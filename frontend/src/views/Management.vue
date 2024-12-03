<script setup lang="ts">
import Excluded from "@/components/Management/Excluded.vue";
import PlatformBinding from "@/components/Management/PlatformBinding.vue";
import PlatformVersions from "@/components/Management/PlatformVersions.vue";
</script>

<template>
  <platform-binding />
  <platform-versions />
  <excluded />
</template>
