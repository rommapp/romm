// Pivot from a metadata value (genre, region, tag, …) into the global
// search scoped to it (`/search?genres=Adventure`), the pivot v1 offered
// from the same rows. Render the result as a link, not a click handler,
// so middle-click / open-in-new-tab work and the chips join keyboard +
// spatial navigation as `a[href]`.
import { ROUTES } from "@/plugins/router";
import type { FilterType } from "@/stores/galleryFilter";

export function searchLocation(filter: FilterType, value: string) {
  return { name: ROUTES.SEARCH, query: { [filter]: value } };
}
