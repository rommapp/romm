import { throttle } from "lodash";
import { onUnmounted, watchEffect, nextTick, type ShallowRef } from "vue";

export const useAutoScroll = (
  scrollContainer: ShallowRef,
  observedElement: ShallowRef,
  options = {},
) => {
  const config = { always: false, smooth: false, deep: false, ...options };
  let isUserScrolled = false;
  let observer: MutationObserver | null = null;

  const scrollToBottom = throttle(() => {
    const containerEl = scrollContainer.value?.$el;
    if (!containerEl) return;

    containerEl.scroll({
      top: containerEl.scrollHeight,
      behavior: config.smooth ? "smooth" : "instant",
    });
  }, 50);

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

    // Auto-scroll on content changes with throttled observer
    observer = new MutationObserver((mutations: MutationRecord[]) => {
      if (!config.always && isUserScrolled) return;

      // Only process if there are actual node additions
      const hasNewNodes = mutations.some(
        (mutation) =>
          mutation.type === "childList" && mutation.addedNodes.length > 0,
      );

      if (hasNewNodes) {
        scrollToBottom();
      }
    });

    observer.observe(observedEl, {
      childList: true,
      subtree: config.deep,
      attributes: false,
      characterData: false,
    });
    scrollToBottom();
  };

  const cleanup = () => {
    scrollToBottom.cancel();
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
