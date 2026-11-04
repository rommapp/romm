import { describe, expect, it } from "vitest";
import { opensInNewContext } from "./mouseGestures";

function click(init: MouseEventInit = {}): MouseEvent {
  return new MouseEvent("click", init);
}

describe("opensInNewContext", () => {
  it("is false for a plain left-click (in-app navigation)", () => {
    expect(opensInNewContext(click())).toBe(false);
  });

  it("is true when Ctrl is held (open in new tab)", () => {
    expect(opensInNewContext(click({ ctrlKey: true }))).toBe(true);
  });

  it("is true when Meta/⌘ is held (open in new tab on macOS)", () => {
    expect(opensInNewContext(click({ metaKey: true }))).toBe(true);
  });

  it("is true when Shift is held (open in new window)", () => {
    expect(opensInNewContext(click({ shiftKey: true }))).toBe(true);
  });

  it("is true when Alt is held (download)", () => {
    expect(opensInNewContext(click({ altKey: true }))).toBe(true);
  });
});
