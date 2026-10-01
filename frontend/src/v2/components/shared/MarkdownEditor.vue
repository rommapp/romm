<script setup lang="ts">
// MarkdownEditor: edit-in-place Markdown surface. md-editor-v3 loads on first
// render (see loadMdEditor), so it stays out of the entry chunk.
import { computed } from "vue";
import { useLazyMarkdown } from "@/v2/composables/useLazyMarkdown";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineOptions({ inheritAttrs: false });

const content = defineModel<string>({ required: true });

const MdEditor = useLazyMarkdown("MdEditor", "12rem");

const { isLight } = useThemeMode();
const theme = computed(() => (isLight.value ? "light" : "dark"));
</script>

<template>
  <component
    :is="MdEditor"
    v-bind="$attrs"
    v-model="content"
    no-highlight
    no-katex
    no-mermaid
    no-echarts
    no-prettier
    no-upload-img
    :theme="theme"
    language="en-US"
    :preview="false"
    :toolbars-exclude="['save', 'github']"
  />
</template>
