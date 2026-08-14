import { afterEach, describe, expect, it } from "vitest";
import { createBodyScrollLock, overlayCount } from "./bodyScrollLock";

afterEach(() => {
  document.body.style.overflow = "";
  delete document.body.dataset.rOverlayOpenCount;
  delete document.body.dataset.rOverlayPrevOverflow;
});

describe("createBodyScrollLock", () => {
  it("locks the body on the first overlay and restores on the last", () => {
    const { lock, unlock } = createBodyScrollLock();
    lock();
    expect(document.body.style.overflow).toBe("hidden");
    expect(overlayCount()).toBe(1);
    unlock();
    expect(document.body.style.overflow).toBe("");
    expect(overlayCount()).toBe(0);
  });

  it("preserves an overflow the host set for its own lifetime", () => {
    document.body.style.overflow = "clip";
    const { lock, unlock } = createBodyScrollLock();
    lock();
    expect(document.body.style.overflow).toBe("hidden");
    unlock();
    expect(document.body.style.overflow).toBe("clip");
  });

  // The bug this module fixes: independent overlays (e.g. a dialog over a
  // drawer) must share one count so the body only unlocks once the LAST
  // one closes, regardless of close order.
  it("keeps the lock while any overlay is still open, in any close order", () => {
    const dialog = createBodyScrollLock();
    const drawer = createBodyScrollLock();

    dialog.lock();
    drawer.lock();
    expect(overlayCount()).toBe(2);
    expect(document.body.style.overflow).toBe("hidden");

    // Close the first-opened overlay first — the body must STAY locked.
    dialog.unlock();
    expect(overlayCount()).toBe(1);
    expect(document.body.style.overflow).toBe("hidden");

    drawer.unlock();
    expect(overlayCount()).toBe(0);
    expect(document.body.style.overflow).toBe("");
  });

  it("is idempotent so an unmount safety-net never double-counts", () => {
    const { lock, unlock } = createBodyScrollLock();
    lock();
    lock(); // duplicate open
    expect(overlayCount()).toBe(1);
    unlock();
    unlock(); // watcher close + onBeforeUnmount
    expect(overlayCount()).toBe(0);
    expect(document.body.style.overflow).toBe("");
  });
});
