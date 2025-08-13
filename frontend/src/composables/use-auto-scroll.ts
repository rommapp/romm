import {
  onUnmounted,
  watchEffect,
  nextTick,
  type Ref,
  type DefineComponent,
} from "vue";

export const useAutoScroll = (
  scrollContainer: Ref<DefineComponent | null>,
  observedElement: Ref<DefineComponent | null>,
  options = {},
) => {
  const config = { always: false, smooth: false, deep: false, ...options };
  let isUserScrolled = false;
  let observer: MutationObserver | null = null;

  const scrollToBottom = () => {
    const containerEl = scrollContainer.value?.$el;
    if (!containerEl) return;

    containerEl.scroll({
      top: containerEl.scrollHeight,
      behavior: config.smooth ? "smooth" : "instant",
    });
  };

  const init = () => {
    const containerEl = scrollContainer.value?.$el;
    const observedEl = observedElement.value?.$el;
    if (!containerEl || !observedEl) return;

    // Track user scrolling
    containerEl.addEventListener("scroll", () => {
      isUserScrolled =
        containerEl.scrollTop + containerEl.clientHeight + 1 <
        containerEl.scrollHeight;
    });

    // Auto-scroll on content changes
    observer = new MutationObserver((e: MutationRecord[]) => {
      if (!config.always && isUserScrolled) return;
      if (e[e.length - 1].addedNodes.length === 0) return;
      scrollToBottom();
    });

    observer.observe(observedEl, { childList: true, subtree: config.deep });
    scrollToBottom();
  };

  const cleanup = () => {
    observer?.disconnect();
    observer = null;
  };

  watchEffect(() => {
    cleanup();
    if (scrollContainer.value && observedElement.value) nextTick(init);
  });

  onUnmounted(cleanup);

  return { scrollToBottom };
};
