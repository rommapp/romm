import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { defineComponent } from "vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { getCoverRatio, setCoverRatio, useGalleryCoverRatios } from "./index";

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

  // Distinct rom ids per test — the ratio store is module-level (shared),
  // so reusing ids across tests would collide. (The `ratioVersion`
  // debounce isn't asserted here: its `setTimeout` doesn't fire under this
  // test harness; the storage / dedup it gates is covered directly below.)
  it("dedups sub-epsilon changes, keeps the first value, updates past it", () => {
    storeGalleryRoms().romIdIndex = [301];
    const { ratioAt, onCardRatio } = withComposable(() =>
      useGalleryCoverRatios(),
    );

    onCardRatio({ romId: 301, ratio: 0.7 });
    expect(ratioAt(0)).toBeCloseTo(0.7);

    onCardRatio({ romId: 301, ratio: 0.705 }); // delta 0.005 < 0.01 → ignored
    expect(ratioAt(0)).toBeCloseTo(0.7);

    onCardRatio({ romId: 301, ratio: 0.9 }); // delta 0.2 ≥ 0.01 → updates
    expect(ratioAt(0)).toBeCloseTo(0.9);
  });
});

describe("getCoverRatio / setCoverRatio (shared store)", () => {
  it("looks up by URL or rom id, normalising a string rom id", () => {
    setCoverRatio({ url: "/covers/401.webp", romId: 401 }, 1.33);

    expect(getCoverRatio({ url: "/covers/401.webp" })).toBeCloseTo(1.33);
    expect(getCoverRatio({ romId: 401 })).toBeCloseTo(1.33);
    // A string id (e.g. a route param) collapses to the numeric key.
    expect(getCoverRatio({ romId: "401" })).toBeCloseTo(1.33);
  });

  it("returns null for unknown keys", () => {
    expect(getCoverRatio({ url: "/covers/missing.webp" })).toBeNull();
    expect(getCoverRatio({ romId: 999999 })).toBeNull();
    expect(getCoverRatio({})).toBeNull();
  });
});
