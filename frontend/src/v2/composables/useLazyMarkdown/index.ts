import { RSkeletonBlock } from "@v2/lib";
import {
  type Component,
  computed,
  defineAsyncComponent,
  h,
  inject,
  type InjectionKey,
  ref,
} from "vue";
import MarkdownLoadError from "@/v2/components/shared/MarkdownLoadError.vue";

export type MarkdownSurface = "preview" | "editor";
type MarkdownLoader = () => Promise<{ default: Component }>;
type MarkdownLoaders = Record<MarkdownSurface, MarkdownLoader>;

// One module per surface, so a preview never downloads CodeMirror.
const LOADERS: MarkdownLoaders = {
  preview: () => import("@/v2/components/shared/markdownPreview"),
  editor: () => import("@/v2/components/shared/markdownEditor"),
};

/** Stories and tests provide loaders to show the loading and error states. The
 *  app never provides it, so the real loaders are used. */
export const MD_LOADERS: InjectionKey<Partial<MarkdownLoaders>> =
  Symbol("MD_LOADERS");

/** Start downloading a surface ahead of its first render. */
export function preloadMarkdown(surface: MarkdownSurface) {
  return LOADERS[surface]();
}

/** Lazy md-editor-v3 component with a skeleton while loading and a retry on failure. */
export function useLazyMarkdown(
  surface: MarkdownSurface,
  skeletonHeight: string,
) {
  const loader = inject(MD_LOADERS, {})[surface] ?? LOADERS[surface];
  const attempt = ref(0);

  // A fresh async component per attempt, since a failed one stays failed.
  return computed(() => {
    void attempt.value;
    return defineAsyncComponent({
      loader,
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
