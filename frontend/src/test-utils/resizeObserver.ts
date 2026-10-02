import { vi } from "vitest";

// happy-dom's ResizeObserver never fires, so tests that depend on resizes
// swap in this one and deliver them by hand.
class FakeResizeObserver implements ResizeObserver {
  static instances = new Set<FakeResizeObserver>();
  readonly targets = new Set<Element>();
  readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    FakeResizeObserver.instances.add(this);
  }

  observe(el: Element) {
    this.targets.add(el);
  }

  unobserve(el: Element) {
    this.targets.delete(el);
  }

  disconnect() {
    this.targets.clear();
  }
}

interface Size {
  width: number;
  height: number;
}

function rect({ width, height }: Size): DOMRectReadOnly {
  const box = { x: 0, y: 0, width, height };
  return {
    ...box,
    top: 0,
    left: 0,
    right: width,
    bottom: height,
    toJSON: () => box,
  };
}

function boxSize({ width, height }: Size): ResizeObserverSize[] {
  return [{ inlineSize: width, blockSize: height }];
}

/** Installs the fake for the current test (`unstubGlobals` removes it after). */
export function stubResizeObserver() {
  FakeResizeObserver.instances.clear();
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);

  return {
    /** Reports `el` at the given content size (and border-box size, which
     *  defaults to the same) to every observer watching it. */
    resize(el: Element, width: number, height = 0, border?: Size) {
      const content = { width, height };
      const entry: ResizeObserverEntry = {
        target: el,
        contentRect: rect(content),
        contentBoxSize: boxSize(content),
        borderBoxSize: boxSize(border ?? content),
        devicePixelContentBoxSize: boxSize(content),
      };
      for (const observer of FakeResizeObserver.instances) {
        if (observer.targets.has(el)) observer.callback([entry], observer);
      }
    },
    /** Whether any observer is still watching `el`. */
    isObserved(el: Element) {
      return [...FakeResizeObserver.instances].some((o) => o.targets.has(el));
    },
  };
}
