// useGalleryViewModeUrl — bookmarkable view-mode (groupBy + layout) via
// URL query params. Sits on top of `useGalleryMode`, which keeps the
// localStorage default for the next session.
//
// Why: per constitution §VI.D, active layout / sort / current-tab
// choices are bookmarkable session state — the URL holds them so a
// copied link reproduces the same view. The localStorage layer
// underneath survives navigation between routes that don't carry the
// param, so the user's preferred default still wins on a fresh view.
//
// Parameter encoding (kept short to keep URLs readable):
//   * ?group=letter   → groupBy = "letter"  (omitted when "none", default)
//   * ?layout=list    → layout  = "list"    (omitted when "grid",  default)
//
// Direction notes mirror useGalleryFilterUrl:
//   * URL → ref fires on every route.query.{group,layout} change
//     (back/forward, pasted URLs, programmatic navigation).
//   * Ref → URL pushes via `router.replace`; comparison guards prevent
//     feedback loops with the URL → ref watcher.
//   * On mount the URL is applied once before the toolbar reads its
//     initial value.
import { onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  type GroupByMode,
  type LayoutMode,
  useGalleryMode,
} from "@/v2/composables/useGalleryMode";

const VALID_GROUP_BY: readonly GroupByMode[] = [
  "letter",
  "family",
  "category",
  "generation",
  "none",
];

function parseGroupBy(value: unknown): GroupByMode | null {
  return typeof value === "string" &&
    (VALID_GROUP_BY as readonly string[]).includes(value)
    ? (value as GroupByMode)
    : null;
}

function parseLayout(value: unknown): LayoutMode | null {
  return value === "grid" || value === "list" ? value : null;
}

export function useGalleryViewModeUrl() {
  const route = useRoute();
  const router = useRouter();
  const { groupBy, layout } = useGalleryMode();

  function applyFromUrl() {
    const g = parseGroupBy(route.query.group);
    const l = parseLayout(route.query.layout);
    if (g !== null && g !== groupBy.value) groupBy.value = g;
    if (l !== null && l !== layout.value) layout.value = l;
  }

  // Mount: pull whatever the URL currently holds into the ref BEFORE the
  // toolbar renders its initial state.
  applyFromUrl();
  onMounted(applyFromUrl);

  watch(() => route.query.group, applyFromUrl);
  watch(() => route.query.layout, applyFromUrl);

  function syncQuery(key: "group" | "layout", value: string | undefined) {
    const current =
      typeof route.query[key] === "string"
        ? (route.query[key] as string)
        : undefined;
    if (value === current) return;
    const nextQuery = { ...route.query };
    if (value === undefined) delete nextQuery[key];
    else nextQuery[key] = value;
    router.replace({ query: nextQuery });
  }

  // Drop the param when the value is the default — keeps URLs clean.
  watch(groupBy, (next) => {
    syncQuery("group", next === "none" ? undefined : next);
  });
  watch(layout, (next) => {
    syncQuery("layout", next === "grid" ? undefined : next);
  });
}
