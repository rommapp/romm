import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope } from "vue";
import { useCssLength } from "./index";

function probes(): HTMLElement[] {
  return [
    ...document.body.querySelectorAll<HTMLElement>("div[aria-hidden]"),
  ].filter((el) => el.style.height === "var(--r-nav-h)");
}

// happy-dom has no layout, so the test plays the browser: it reports the
// probe's resolved border-box height the way a ResizeObserver would.
function stubResizeObserver() {
  class FakeResizeObserver implements ResizeObserver {
    targets: Element[] = [];
    callback: ResizeObserverCallback;
    constructor(callback: ResizeObserverCallback) {
      this.callback = callback;
      observers.push(this);
    }
    observe(target: Element) {
      this.targets.push(target);
    }
    unobserve() {}
    disconnect() {
      this.targets = [];
    }
  }
  const observers: FakeResizeObserver[] = [];
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  return (target: Element, blockSize: number) => {
    const size: ResizeObserverSize = { inlineSize: 0, blockSize };
    const entry: ResizeObserverEntry = {
      target,
      borderBoxSize: [size],
      contentBoxSize: [size],
      devicePixelContentBoxSize: [size],
      contentRect: new DOMRectReadOnly(0, 0, 0, blockSize),
    };
    for (const observer of observers) {
      if (observer.targets.includes(target))
        observer.callback([entry], observer);
    }
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useCssLength", () => {
  it("sizes a probe by the expression and removes it on dispose", () => {
    const scope = effectScope();
    try {
      const length = scope.run(() => useCssLength("var(--r-nav-h)"));
      expect(probes()).toHaveLength(1);
      expect(length?.value).toBe(0);
    } finally {
      scope.stop();
    }
    expect(probes()).toHaveLength(0);
  });

  it("tracks the probe's resolved height as it changes", () => {
    const resize = stubResizeObserver();
    const scope = effectScope();
    try {
      const length = scope.run(() => useCssLength("var(--r-nav-h)"));
      const [probe] = probes();
      expect(probe).toBeDefined();

      resize(probe!, 105);
      expect(length?.value).toBe(105);

      resize(probe!, 58);
      expect(length?.value).toBe(58);
    } finally {
      scope.stop();
    }
  });
});
