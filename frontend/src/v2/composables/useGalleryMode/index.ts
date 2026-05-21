// useGalleryMode — global gallery-view preferences backed by localStorage.
// Two orthogonal axes control how roms render in Platform / Collection /
// Search, plus a toolbar-placement preference that layouts read.
//
//   * groupBy          — "letter" | "family" | "category" | "generation"
//                        | "none" (default "none")
//   * layout           — "grid"   | "list"   (default "grid")
//   * toolbarPosition  — "header" | "floating" (default "header")
//
// Persistence is global (one set of prefs across galleries — matches v1).
//
// Trade-off on the extended `groupBy`: "family" / "category" /
// "generation" are platform-specific and only meaningful in
// PlatformsIndex. ROM galleries (Platform / Collection / Search) only
// recognise "letter" and treat everything else as flat — so a user who
// picked "by family" on Platforms and then opens a ROM gallery sees a
// flat layout with no indicator highlighted. The alternative (per-view
// groupBy state) would break the "one consistent reading mode" contract
// this composable is built around, so we accept the minor inconsistency.
import { useLocalStorage, type RemovableRef } from "@vueuse/core";

export type GroupByMode =
  | "letter"
  | "family"
  | "category"
  | "generation"
  | "playable"
  | "none";
export type LayoutMode = "grid" | "list";
export type ToolbarPosition = "header" | "floating";

const groupBy = useLocalStorage<GroupByMode>("v2.gallery.groupBy", "none");
const layout = useLocalStorage<LayoutMode>("v2.gallery.layout", "grid");
const toolbarPosition = useLocalStorage<ToolbarPosition>(
  "v2.gallery.toolbarPosition",
  "header",
);

export interface GalleryMode {
  groupBy: RemovableRef<GroupByMode>;
  layout: RemovableRef<LayoutMode>;
  toolbarPosition: RemovableRef<ToolbarPosition>;
}

export function useGalleryMode(): GalleryMode {
  return { groupBy, layout, toolbarPosition };
}
