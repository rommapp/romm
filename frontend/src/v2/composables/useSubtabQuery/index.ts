// Binds a details tab's active subtab to the route's `?subtab=` param.
import { shallowRef, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { syncQueryParam } from "@/v2/utils/routeQuery";

export function useSubtabQuery<T extends string>(
  tabId: string,
  isValid: (value: string) => boolean,
  fallback: T,
): Ref<T> {
  const route = useRoute();
  const router = useRouter();

  // A tab mounting mid-switch still sees the previous tab's subtab in the URL.
  function urlSubtab(): string | null {
    const raw = route.query.subtab;
    return route.query.tab === tabId && typeof raw === "string" ? raw : null;
  }

  function fromRoute(): T | null {
    const raw = urlSubtab();
    return raw !== null && isValid(raw) ? (raw as T) : null;
  }

  // `shallowRef` cannot resolve its unwrap type for a generic `T`.
  const subtab = shallowRef(fromRoute() ?? fallback) as Ref<T>;

  watch(subtab, (value) => syncQueryParam(router, "subtab", value));

  watch([() => route.query.tab, () => route.query.subtab], () => {
    const value = fromRoute();
    if (value !== null && value !== subtab.value) subtab.value = value;
  });

  // A subtab the URL names but the view can't show (a stale or hand-edited
  // link) is rewritten to the one on screen.
  watch(
    () => {
      const raw = urlSubtab();
      return raw !== null && !isValid(raw);
    },
    (invalid) => {
      if (invalid && isValid(subtab.value)) {
        syncQueryParam(router, "subtab", subtab.value);
      }
    },
    { immediate: true },
  );

  return subtab;
}
