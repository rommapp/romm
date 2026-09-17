// Binds a details tab's active subtab to the route's `?subtab=` param.
import { shallowRef, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";

export function useSubtabQuery<T extends string>(
  tabId: string,
  isValid: (value: string) => boolean,
  fallback: T,
): Ref<T> {
  const route = useRoute();
  const router = useRouter();

  // A tab mounting mid-switch still sees the previous tab's subtab in the URL.
  function fromRoute(): T | null {
    const raw = route.query.subtab;
    if (route.query.tab !== tabId || typeof raw !== "string") return null;
    return isValid(raw) ? (raw as T) : null;
  }

  // `shallowRef` cannot resolve its unwrap type for a generic `T`.
  const subtab = shallowRef(fromRoute() ?? fallback) as Ref<T>;

  watch(subtab, (value) => {
    if (route.query.subtab === value) return;
    void router.replace({
      path: route.path,
      query: { ...route.query, subtab: value },
    });
  });

  watch(
    () => [route.query.tab, route.query.subtab],
    () => {
      const value = fromRoute();
      if (value !== null && value !== subtab.value) subtab.value = value;
    },
  );

  return subtab;
}
