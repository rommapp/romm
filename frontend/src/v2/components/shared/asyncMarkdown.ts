import { RSpinner } from "@v2/lib";
import { defineAsyncComponent, defineComponent, h } from "vue";

// Vue passes the wrapped component's attrs to the loading component; drop them.
const MdLoading = defineComponent({
  inheritAttrs: false,
  render: () => h(RSpinner),
});

export const loadMdPreview = () => import("./markdownPreview");

// md-editor stays out of the importing chunk until the first render.
export const AsyncMdPreview = defineAsyncComponent({
  loader: loadMdPreview,
  loadingComponent: MdLoading,
});

export const AsyncMdEditor = defineAsyncComponent({
  loader: () => import("./markdownEditor"),
  loadingComponent: MdLoading,
});
