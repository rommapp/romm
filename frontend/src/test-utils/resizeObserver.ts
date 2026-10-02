import { vi } from "vitest";

// happy-dom's ResizeObserver never fires, so tests that depend on resizes
// swap in this one and deliver them by hand.
class FakeResizeObserver {
  static live = new Set<FakeResizeObserver>();
  readonly targets = new Set<Element>();
  readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    FakeResizeObserver.live.add(this);
  }

  observe(el: Element) {
    this.targets.add(el);
  }

  unobserve(el: Element) {
    this.targets.delete(el);
  }

  disconnect() {
    this.targets.clear();
    FakeResizeObserver.live.delete(this);
  }
}

/** Installs the fake for the current test; undo with `vi.unstubAllGlobals()`. */
export function stubResizeObserver() {
  FakeResizeObserver.live.clear();
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);

  return {
    /** Reports `el` at the given content size (and border-box size, which
     *  defaults to the same) to every observer watching it. */
    resize(
      el: Element,
      width: number,
      height = 0,
      border: { width: number; height: number } = { width, height },
    ) {
      const entry = {
        target: el,
        contentRect: { width, height },
        contentBoxSize: [{ inlineSize: width, blockSize: height }],
        borderBoxSize: [{ inlineSize: border.width, blockSize: border.height }],
      } as unknown as ResizeObserverEntry;
      for (const observer of [...FakeResizeObserver.live]) {
        if (observer.targets.has(el)) {
          observer.callback([entry], observer as unknown as ResizeObserver);
        }
      }
    },
    /** Whether any live observer is still watching `el`. */
    isObserved(el: Element) {
      return [...FakeResizeObserver.live].some((o) => o.targets.has(el));
    },
  };
}
