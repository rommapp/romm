import { RSkeletonBlock } from "@v2/lib";
import { computed, defineAsyncComponent, h, inject, ref } from "vue";
import { MD_EDITOR_LOADER, loadMdEditor } from "@/plugins/mdeditor";
import MarkdownLoadError from "@/v2/components/shared/MarkdownLoadError.vue";

/** Lazy md-editor-v3 component with a skeleton while loading and a retry on failure. */
export function useLazyMarkdown(
  name: "MdEditor" | "MdPreview",
  skeletonHeight: string,
) {
  const loader = inject(MD_EDITOR_LOADER, loadMdEditor);
  const attempt = ref(0);

  // A fresh async component per attempt, since a failed one stays failed.
  return computed(() => {
    void attempt.value;
    return defineAsyncComponent({
      loader: () => loader().then((m) => m[name]),
      loadingComponent: {
        render: () => h(RSkeletonBlock, { height: skeletonHeight }),
      },
      errorComponent: {
        render: () => h(MarkdownLoadError, { onRetry: () => attempt.value++ }),
      },
      // Only show the skeleton when the chunk is slow to arrive.
      delay: 200,
    });
  });
}
