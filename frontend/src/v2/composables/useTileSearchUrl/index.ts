// useTileSearchUrl: the index views' tile search, bookmarkable via `?search=`.
import type { Ref } from "vue";
import { useRouteQueryParam } from "@/v2/composables/useRouteQueryParam";

export function useTileSearchUrl(): Ref<string> {
  return useRouteQueryParam("search");
}
