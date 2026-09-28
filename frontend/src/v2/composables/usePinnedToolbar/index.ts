import { useWindowScroll } from "@vueuse/core";
import {
  type ComponentPublicInstance,
  computed,
  onBeforeUnmount,
  type Ref,
  ref,
  watch,
} from "vue";
import { useNavGlass } from "@/v2/composables/useNavGlass";

// An element's layout position on the page, unaffected by scrolling.
function pageTop(el: HTMLElement): number {
  let top = 0;
  let node: HTMLElement | null = el;
  while (node) {
    top += node.offsetTop;
    node = node.offsetParent as HTMLElement | null;
  }
  return top;
}

/**
 * Tracks a toolbar pinned under the top bar and hands it the bar's glass.
 *
 * Args:
 *   scrollTop: the inner scroller's offset; omit it when the page scrolls.
 */
export function usePinnedToolbar(scrollTop?: Ref<number>) {
  const scrolled = scrollTop ?? useWindowScroll().y;
  const toolbarEl = ref<HTMLElement | null>(null);
  // Zero-height element right before the toolbar: a sticky element's own
  // offsetTop reports its pinned position, so this marks its natural top.
  const sentinelEl = ref<HTMLElement | null>(null);
  const toolbarHeight = ref(0);
  const naturalTop = ref(0);
  // The toolbar's sticky `top` (the top bar's height), read from its style.
  const pinnedTop = ref(0);
  let observer: ResizeObserver | null = null;
  let observed: Element[] = [];

  function measure() {
    const toolbar = toolbarEl.value;
    const sentinel = sentinelEl.value;
    if (!toolbar || !sentinel) return;
    toolbarHeight.value = toolbar.getBoundingClientRect().height;
    pinnedTop.value = parseFloat(getComputedStyle(toolbar).top) || 0;
    naturalTop.value = scrollTop ? sentinel.offsetTop : pageTop(sentinel);
  }

  // The toolbar, the sentinel and the earlier siblings (the header) that move it.
  function observedElements(): Element[] {
    const toolbar = toolbarEl.value;
    const sentinel = sentinelEl.value;
    if (!toolbar || !sentinel) return [];
    const out: Element[] = [toolbar];
    let el: Element | null = sentinel;
    while (el) {
      out.push(el);
      el = el.previousElementSibling;
    }
    return out;
  }

  // Vue calls function refs on every re-render (the virtual scroller re-renders
  // while scrolling), so re-observe and re-measure only when the elements change.
  function sync() {
    const next = observedElements();
    if (
      next.length === observed.length &&
      next.every((el, i) => el === observed[i])
    ) {
      return;
    }
    observed = next;
    observer?.disconnect();
    observer = null;
    if (next.length === 0) {
      toolbarHeight.value = 0;
      pinnedTop.value = 0;
      naturalTop.value = 0;
      return;
    }
    measure();
    observer = new ResizeObserver(measure);
    for (const el of next) observer.observe(el);
  }

  function bindToolbar(el: Element | ComponentPublicInstance | null) {
    toolbarEl.value = (el as HTMLElement | null) ?? null;
    sync();
  }
  function bindSentinel(el: Element | ComponentPublicInstance | null) {
    sentinelEl.value = (el as HTMLElement | null) ?? null;
    sync();
  }

  /** How far the scroller travels before the toolbar pins. */
  const pinDistance = computed(() =>
    Math.max(0, naturalTop.value - pinnedTop.value),
  );
  // Without a toolbar (the floating dock) nothing can take the top bar's glass.
  const pinned = computed(
    () =>
      toolbarEl.value !== null &&
      scrolled.value > 0 &&
      scrolled.value >= pinDistance.value,
  );

  // The top bar turns to glass as soon as content scrolls under it (an inner
  // scroller reports that itself); the toolbar takes that glass over once pinned.
  const { innerScrolled, innerGlass, handoff, threshold } = useNavGlass();
  handoff.value = true;
  if (scrollTop) {
    watch(
      () => scrollTop.value > threshold,
      (value) => (innerScrolled.value = value),
      { immediate: true },
    );
  }
  watch(pinned, (value) => (innerGlass.value = value), { immediate: true });

  onBeforeUnmount(() => {
    observer?.disconnect();
    observer = null;
    innerScrolled.value = false;
    innerGlass.value = false;
    handoff.value = false;
  });

  return {
    toolbarHeight,
    pinDistance,
    pinned,
    bindToolbar,
    bindSentinel,
  };
}
