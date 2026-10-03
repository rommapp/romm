<script setup lang="ts">
// MdPreview, its stylesheet and config as one lazy-loadable chunk; attrs fall through.
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import "@/plugins/mdeditor";
</script>

<template>
  <MdPreview />
</template>
