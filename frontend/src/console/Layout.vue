<template>
  <div class="min-h-screen text-white console-root">
    <router-view />
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
// Import Tailwind v4 entry so utilities are available when this layout renders
import './index.css';
onMounted(() => document.body.classList.add('console-mode'));
onUnmounted(() => document.body.classList.remove('console-mode'));
</script>
<style></style>
