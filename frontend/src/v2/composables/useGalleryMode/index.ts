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
//
// Letter grouping in a ROM gallery also depends on the active sort axis:
// the server only indexes letters for a lexically ordered result, so the
// two move together through `resolveGroupBy` / `orderKeyForGroupBy`.
import { useLocalStorage, type RemovableRef } from "@vueuse/core";
import {
  DEFAULT_ORDER_BY,
  isLexicalOrderKey,
  type GalleryOrderKey,
} from "@/v2/stores/galleryRoms";

export const GROUP_BY_MODES = [
  "letter",
  "family",
  "category",
  "generation",
  "playable",
  "none",
] as const;

export type GroupByMode = (typeof GROUP_BY_MODES)[number];
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

/** Narrows an untrusted string (a URL query param) to a group-by mode. */
export function isGroupByMode(value: string): value is GroupByMode {
  return (GROUP_BY_MODES as readonly string[]).includes(value);
}

/** The grouping a ROM gallery can actually render: letter buckets need the
 *  server's char index, so any other axis reads as flat while leaving the
 *  stored preference alone. */
export function resolveGroupBy(
  mode: GroupByMode,
  orderBy: GalleryOrderKey,
): GroupByMode {
  return mode === "letter" && !isLexicalOrderKey(orderBy) ? "none" : mode;
}

/** The axis a group-by pick implies: asking for letter buckets is asking to
 *  sort lexically, so a non-lexical axis snaps back to the default. */
export function orderKeyForGroupBy(
  mode: GroupByMode,
  orderBy: GalleryOrderKey,
): GalleryOrderKey {
  return mode === "letter" && !isLexicalOrderKey(orderBy)
    ? DEFAULT_ORDER_BY
    : orderBy;
}
