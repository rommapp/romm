// Binds a ref to one `?key=` query param. A missing or unknown value reads as
// the fallback, and the fallback is left out of the URL.
import { ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { syncQueryParam } from "@/v2/utils/routeQuery";

export function useRouteQueryParam(key: string, fallback?: string): Ref<string>;
export function useRouteQueryParam<T extends string>(
  key: string,
  fallback: T,
  values: readonly T[],
): Ref<T>;
export function useRouteQueryParam(
  key: string,
  fallback = "",
  values?: readonly string[],
): Ref<string> {
  const route = useRoute();
  const router = useRouter();

  function fromRoute(): string {
    const raw = route.query[key];
    return typeof raw === "string" && (!values || values.includes(raw))
      ? raw
      : fallback;
  }

  const state = ref(fromRoute());

  watch(
    () => route.query[key],
    () => {
      const next = fromRoute();
      if (next !== state.value) state.value = next;
    },
  );

  watch(state, (value) =>
    syncQueryParam(router, key, value === fallback ? undefined : value),
  );

  return state;
}
