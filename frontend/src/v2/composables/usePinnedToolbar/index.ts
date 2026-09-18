import {
  type ComponentPublicInstance,
  computed,
  onBeforeUnmount,
  type Ref,
  ref,
  watch,
} from "vue";
import { useNavGlass } from "@/v2/composables/useNavGlass";

/**
 * A sticky toolbar inside a scroller that pins right under the top bar (the
 * gallery shells): measures where it pins, tells when it is pinned, and hands
 * the top bar's glass to it while pinned.
 *
 * Bind `bindToolbar` to the toolbar and `bindSentinel` to a zero-height,
 * non-sticky element right before it: a sticky element's own offsetTop reports
 * its pinned position, so the sentinel is what marks its natural top.
 */
export function usePinnedToolbar(scrollTop: Ref<number>) {
  const toolbarEl = ref<HTMLElement | null>(null);
  const sentinelEl = ref<HTMLElement | null>(null);
  const toolbarHeight = ref(0);
  const naturalTop = ref(0);
  // The toolbar's sticky `top` (the top bar's height), read from its style.
  const pinnedTop = ref(0);
  let observer: ResizeObserver | null = null;

  function measure() {
    const toolbar = toolbarEl.value;
    toolbarHeight.value = toolbar?.getBoundingClientRect().height ?? 0;
    pinnedTop.value = toolbar
      ? parseFloat(getComputedStyle(toolbar).top) || 0
      : 0;
    naturalTop.value = sentinelEl.value?.offsetTop ?? 0;
  }

  function rebuild() {
    observer?.disconnect();
    observer = null;
    measure();
    if (!toolbarEl.value && !sentinelEl.value) return;
    observer = new ResizeObserver(measure);
    if (toolbarEl.value) observer.observe(toolbarEl.value);
    // Earlier siblings (the header) move the sentinel when they resize.
    let prev = sentinelEl.value?.previousElementSibling;
    while (prev) {
      observer.observe(prev);
      prev = prev.previousElementSibling;
    }
  }

  // Use these as STABLE function refs (never inline arrows): an inline ref has
  // a new identity every render, so Vue re-binds it with `null` then the
  // element on every re-render, and the shells re-render on every scroll frame.
  function bindToolbar(el: Element | ComponentPublicInstance | null) {
    toolbarEl.value = (el as HTMLElement | null) ?? null;
    rebuild();
  }
  function bindSentinel(el: Element | ComponentPublicInstance | null) {
    sentinelEl.value = (el as HTMLElement | null) ?? null;
    rebuild();
  }

  /** How far the scroller travels before the toolbar pins. */
  const pinDistance = computed(() =>
    Math.max(0, naturalTop.value - pinnedTop.value),
  );
  const pinned = computed(
    () => scrollTop.value > 0 && scrollTop.value >= pinDistance.value,
  );

  // The top bar turns to glass as soon as the scroller moves (content passes
  // under it); the toolbar takes that glass over once pinned.
  const { innerScrolled, innerGlass, threshold } = useNavGlass();
  watch(
    () => scrollTop.value > threshold,
    (value) => (innerScrolled.value = value),
    { immediate: true },
  );
  watch(pinned, (value) => (innerGlass.value = value), { immediate: true });

  onBeforeUnmount(() => {
    observer?.disconnect();
    observer = null;
    innerScrolled.value = false;
    innerGlass.value = false;
  });

  return {
    toolbarEl,
    toolbarHeight,
    pinnedTop,
    pinDistance,
    pinned,
    bindToolbar,
    bindSentinel,
  };
}
