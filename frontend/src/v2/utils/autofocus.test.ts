import { afterEach, describe, expect, it, vi } from "vitest";
import { useInputModality } from "@/v2/composables/useInputModality";
import {
  focusFromInput,
  shouldAutofocusSearch,
  shouldClaimFocusOnModality,
} from "./autofocus";

function fakeWindow(matches: boolean): Window {
  return {
    matchMedia: (media: string) => ({ matches, media }),
  } as unknown as Window;
}

describe("shouldAutofocusSearch", () => {
  it("autofocuses on precise-pointer devices (hover + fine pointer)", () => {
    expect(shouldAutofocusSearch(fakeWindow(true))).toBe(true);
  });

  it("skips autofocus on touch-primary devices (no hover / coarse pointer)", () => {
    // The Android-keyboard fix: a tap must not pop the on-screen keyboard.
    expect(shouldAutofocusSearch(fakeWindow(false))).toBe(false);
  });

  it("defaults to autofocus when matchMedia is unavailable (SSR / old env)", () => {
    expect(shouldAutofocusSearch(undefined)).toBe(true);
    expect(shouldAutofocusSearch({} as unknown as Window)).toBe(true);
  });
});

describe("shouldClaimFocusOnModality", () => {
  const body = document.body;
  const button = document.createElement("button");

  it("claims an unfocused page for a pad or a keyboard", () => {
    expect(shouldClaimFocusOnModality("pad", body, body)).toBe(true);
    expect(shouldClaimFocusOnModality("key", null, body)).toBe(true);
  });

  it("leaves a focused element alone", () => {
    expect(shouldClaimFocusOnModality("pad", button, body)).toBe(false);
  });

  it("ignores devices that do not navigate by focus", () => {
    expect(shouldClaimFocusOnModality("mouse", body, body)).toBe(false);
    expect(shouldClaimFocusOnModality("touch", body, body)).toBe(false);
  });
});

describe("focusFromInput", () => {
  const { setModality } = useInputModality();
  afterEach(() => setModality("mouse"));

  it.each(["key", "pad"] as const)(
    "asks for a visible focus ring on %s input",
    (modality) => {
      setModality(modality);
      const el = { focus: vi.fn() };

      focusFromInput(el, { preventScroll: true });

      expect(el.focus).toHaveBeenCalledWith({
        preventScroll: true,
        focusVisible: true,
      });
    },
  );

  it.each(["mouse", "touch"] as const)(
    "leaves the ring to the browser on %s input",
    (modality) => {
      setModality(modality);
      const el = { focus: vi.fn() };

      focusFromInput(el);

      expect(el.focus).toHaveBeenCalledWith({});
    },
  );

  it("ignores a missing element", () => {
    expect(() => focusFromInput(null)).not.toThrow();
  });
});
