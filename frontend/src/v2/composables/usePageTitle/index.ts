// usePageTitle
//
// Keeps `document.title` in sync with a reactive source. Views whose title
// depends on fetched data need this rather than the router's `meta.title`,
// which is resolved in the navigation guard before the data lands (and, on
// param-only navigations like /rom/1 -> /rom/2, doesn't re-run the view).
//
// The title is deliberately not restored on unmount: the router guard has
// already set the next route's title by the time a view tears down.
import { watch } from "vue";

const DEFAULT_TITLE = "RomM";

export function usePageTitle(source: () => string | null | undefined) {
  watch(
    source,
    (title) => {
      document.title = title || DEFAULT_TITLE;
    },
    { immediate: true },
  );
}
