<script setup lang="ts">
import Excluded from "@/layouts/Management/Excluded.vue";
import PlatformBinding from "@/layouts/Management/PlatformBinding.vue";
import PlatformVersions from "@/layouts/Management/PlatformVersions.vue";
</script>

<template>
  <platform-binding />
  <platform-versions />
  <excluded />
</template>
