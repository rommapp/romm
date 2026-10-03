<script setup lang="ts">
// MdPreview and its stylesheet as one lazy-loadable chunk; attrs fall through.
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
</script>

<template>
  <MdPreview />
</template>
