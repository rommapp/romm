<script setup lang="ts">
// MarkdownPreview: read-only Markdown surface. md-editor-v3 loads on first
// render (see loadMdEditor), so it stays out of the entry chunk.
import { RSkeletonBlock } from "@v2/lib";
import { computed, defineAsyncComponent, h, inject } from "vue";
import { MD_EDITOR_LOADER, loadMdEditor } from "@/plugins/mdeditor";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineOptions({ inheritAttrs: false });

defineProps<{ modelValue: string }>();

const loader = inject(MD_EDITOR_LOADER, loadMdEditor);

const MdPreview = defineAsyncComponent({
  loader: () => loader().then((m) => m.MdPreview),
  loadingComponent: { render: () => h(RSkeletonBlock, { height: "4rem" }) },
  // Only show the skeleton when the chunk is slow to arrive.
  delay: 200,
});

const { isLight } = useThemeMode();
const theme = computed(() => (isLight.value ? "light" : "dark"));

// The library's default id is the raw heading text, spaces included, which is
// not a valid id and breaks in-page anchors.
function headingId({ text, index }: { text: string; index: number }) {
  const slug = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "");
  return `${slug || "heading"}-${index}`;
}
</script>

<template>
  <MdPreview
    v-bind="$attrs"
    no-highlight
    no-katex
    no-mermaid
    no-echarts
    :md-heading-id="headingId"
    :model-value="modelValue"
    :theme="theme"
    language="en-US"
    preview-theme="vuepress"
    code-theme="github"
  />
</template>
