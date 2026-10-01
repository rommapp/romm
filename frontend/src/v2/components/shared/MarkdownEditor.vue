<script setup lang="ts">
// MarkdownEditor: edit-in-place Markdown surface. md-editor-v3 loads on first
// render (see loadMdEditor), so it stays out of the entry chunk.
import { RSkeletonBlock } from "@v2/lib";
import { computed, defineAsyncComponent, h } from "vue";
import { loadMdEditor } from "@/plugins/mdeditor";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineOptions({ inheritAttrs: false });

const content = defineModel<string>({ required: true });

const MdEditor = defineAsyncComponent({
  loader: () => loadMdEditor().then((m) => m.MdEditor),
  loadingComponent: { render: () => h(RSkeletonBlock, { height: "12rem" }) },
  // Only show the skeleton when the chunk is slow to arrive.
  delay: 200,
});

const { isLight } = useThemeMode();
const theme = computed(() => (isLight.value ? "light" : "dark"));
</script>

<template>
  <MdEditor
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
