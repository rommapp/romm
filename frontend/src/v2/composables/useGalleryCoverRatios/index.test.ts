import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { useGalleryCoverRatios } from "./index";

// Run the composable inside a real component so its `onBeforeUnmount`
// cleanup has a host instance. Returns the composable's result.
function withComposable<T>(fn: () => T): T {
  let result!: T;
  mount(
    defineComponent({
      setup() {
        result = fn();
        return () => null;
      },
    }),
  );
  return result;
}

describe("useGalleryCoverRatios", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("ratioAt maps position → rom id → measured ratio, else 0", () => {
    storeGalleryRoms().romIdIndex = [101, 102, 103];
    const { ratioAt, onCardRatio } = withComposable(() =>
      useGalleryCoverRatios(),
    );

    expect(ratioAt(1)).toBe(0); // not yet measured
    expect(ratioAt(99)).toBe(0); // position outside the index

    onCardRatio({ romId: 102, ratio: 1.2 });
    expect(ratioAt(1)).toBeCloseTo(1.2); // position 1 → rom 102
    expect(ratioAt(0)).toBe(0); // rom 101 still unmeasured
  });

  it("bumps ratioVersion once per debounce burst", () => {
    storeGalleryRoms().romIdIndex = [101, 102];
    const { ratioVersion, onCardRatio } = withComposable(() =>
      useGalleryCoverRatios(),
    );

    expect(ratioVersion.value).toBe(0);
    onCardRatio({ romId: 101, ratio: 0.7 });
    onCardRatio({ romId: 102, ratio: 0.5 });
    expect(ratioVersion.value).toBe(0); // still debouncing

    vi.advanceTimersByTime(350);
    expect(ratioVersion.value).toBe(1); // one bump for the whole burst
  });

  it("ignores sub-epsilon changes (no re-store, no extra re-pack)", () => {
    storeGalleryRoms().romIdIndex = [101];
    const { ratioVersion, ratioAt, onCardRatio } = withComposable(() =>
      useGalleryCoverRatios(),
    );

    onCardRatio({ romId: 101, ratio: 0.7 });
    vi.advanceTimersByTime(350);
    expect(ratioVersion.value).toBe(1);
    expect(ratioAt(0)).toBeCloseTo(0.7);

    onCardRatio({ romId: 101, ratio: 0.705 }); // delta 0.005 < 0.01
    vi.advanceTimersByTime(350);
    expect(ratioVersion.value).toBe(1); // no new bump
    expect(ratioAt(0)).toBeCloseTo(0.7); // value unchanged
  });
});
