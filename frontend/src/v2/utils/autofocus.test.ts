import { describe, expect, it } from "vitest";
import { shouldAutofocusSearch, shouldClaimFocusOnModality } from "./autofocus";

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
