// Shared, reference-counted body scroll lock for v2 overlays.
//
// Every overlay that covers the page (RDialog, RDrawer, ...) hides the
// body scrollbar while open. They MUST share a single counter and a
// single saved-overflow value: with per-type counters, a dialog stacked
// over a drawer (or vice versa) would restore `body` overflow off its
// own count and clobber the other's lock — leaving the page scrollable
// while an overlay is still open, or permanently locked after all close.
//
// The first overlay to open snapshots whatever overflow was already in
// effect (e.g. a gallery view that locks the body for its whole
// lifetime) and forces "hidden"; the last one to close restores that
// snapshot instead of clobbering it to "". State lives on
// `document.body.dataset` so it survives across the many independent
// component instances that share the count.

const COUNT_KEY = "rOverlayOpenCount";
const PREV_OVERFLOW_KEY = "rOverlayPrevOverflow";

/** Number of overlays currently holding the lock. */
export function overlayCount(): number {
  return Number(document.body.dataset[COUNT_KEY] ?? "0");
}

// Each caller gets its own idempotent lock/unlock pair: `holdsLock`
// guards against double-counting so an unmount safety net can always
// call unlock() even when the close path already ran (and vice versa).
export function createBodyScrollLock() {
  let holdsLock = false;

  function lock(): void {
    if (holdsLock) return;
    holdsLock = true;
    const cur = overlayCount() + 1;
    document.body.dataset[COUNT_KEY] = String(cur);
    if (cur === 1) {
      document.body.dataset[PREV_OVERFLOW_KEY] = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
  }

  function unlock(): void {
    if (!holdsLock) return;
    holdsLock = false;
    const cur = Math.max(0, overlayCount() - 1);
    document.body.dataset[COUNT_KEY] = String(cur);
    if (cur === 0) {
      document.body.style.overflow =
        document.body.dataset[PREV_OVERFLOW_KEY] ?? "";
      delete document.body.dataset[PREV_OVERFLOW_KEY];
    }
  }

  return { lock, unlock };
}
