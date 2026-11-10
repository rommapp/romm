import { useElementSize, useIntersectionObserver } from "@vueuse/core";
import {
  computed,
  onScopeDispose,
  ref,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
} from "vue";

const navEl = shallowRef<HTMLElement | null>(null);
const collapsedTitle = ref("");
let owner: symbol | undefined;

export function useNavTitle() {
  return { navEl, collapsedTitle };
}

export function useCollapsingTitle(
  heading: Ref<HTMLElement | null>,
  title: MaybeRefOrGetter<string | undefined>,
) {
  const id = Symbol();
  owner = id;
  collapsedTitle.value = "";
  const { height } = useElementSize(navEl, undefined, { box: "border-box" });
  const hiddenAbove = ref(false);
  const rootMargin = computed(() => `-${height.value}px 0px 0px 0px`);
  useIntersectionObserver(
    heading,
    ([entry]) => {
      if (entry)
        hiddenAbove.value =
          !entry.isIntersecting &&
          entry.boundingClientRect.bottom <= height.value;
    },
    { rootMargin },
  );

  // Keep the compact label current when metadata or the language changes.
  const label = computed(() =>
    hiddenAbove.value ? (toValue(title) ?? "") : "",
  );
  watch(
    label,
    (value) => {
      if (owner === id) collapsedTitle.value = value;
    },
    { immediate: true },
  );
  onScopeDispose(() => {
    if (owner === id) {
      owner = undefined;
      collapsedTitle.value = "";
    }
  });
}
