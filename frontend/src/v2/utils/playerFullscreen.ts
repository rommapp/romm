import Bowser from "bowser";

// iOS Safari exposes no Fullscreen API on non-video elements, so EmulatorJS's
// fullscreen button is inert there. We emulate just enough of the API for it
// to drive a fixed, viewport-filling stage.
//
// v2 needs no nav-hiding counterpart: the player calls useStageActive, which
// unmounts AppNav and BottomNav for the duration of the session.
const FULLSCREEN_STYLE = `
  [data-ios-fullscreen-active] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100svh !important;
    z-index: 99999 !important;
    background: var(--r-color-canvas-bg) !important;
  }
`;

function isShimRequired() {
  const osName = Bowser.getParser(navigator.userAgent).getOSName(true);
  return (
    osName === "ios" ||
    // iPadOS 13+ reports as macOS with touch support, so fall back to that check.
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

/**
 * Patches the Fullscreen API on iOS so the in-player fullscreen control works.
 *
 * Returns: a disposer that exits the emulated fullscreen and restores every
 * patched property. A no-op on platforms with real fullscreen support.
 */
export function installIOSFullscreenShim(): () => void {
  if (!isShimRequired()) {
    return () => {};
  }

  const proto = HTMLElement.prototype;
  const overrides: Array<{
    target: object;
    key: PropertyKey;
    prev?: PropertyDescriptor;
  }> = [];
  const override = (
    target: object,
    key: PropertyKey,
    descriptor: PropertyDescriptor,
  ) => {
    overrides.push({
      target,
      key,
      prev: Object.getOwnPropertyDescriptor(target, key),
    });
    Object.defineProperty(target, key, { configurable: true, ...descriptor });
  };

  const styleEl = document.createElement("style");
  styleEl.textContent = FULLSCREEN_STYLE;
  document.head.appendChild(styleEl);

  let fullscreenElement: HTMLElement | null = null;

  const dispatchChange = (target: HTMLElement) => {
    document.dispatchEvent(new Event("fullscreenchange"));
    target.dispatchEvent(new Event("fullscreenchange"));
  };

  const enter = (el: HTMLElement) => {
    if (fullscreenElement === el) return Promise.resolve();
    if (fullscreenElement) void exit();

    el.setAttribute("data-ios-fullscreen-active", "");
    fullscreenElement = el;
    dispatchChange(el);
    return Promise.resolve();
  };

  const exit = () => {
    const el = fullscreenElement;
    if (!el) return Promise.resolve();
    el.removeAttribute("data-ios-fullscreen-active");
    fullscreenElement = null;
    dispatchChange(el);
    return Promise.resolve();
  };

  override(document, "fullscreenEnabled", { get: () => true });
  override(document, "fullscreenElement", { get: () => fullscreenElement });
  override(document, "exitFullscreen", { value: exit, writable: true });
  override(proto, "requestFullscreen", {
    value: function (this: HTMLElement) {
      return enter(this);
    },
    writable: true,
  });
  override(proto, "webkitRequestFullscreen", {
    value: function (this: HTMLElement) {
      void enter(this);
    },
    writable: true,
  });

  return () => {
    void exit();
    styleEl.remove();
    while (overrides.length) {
      const { target, key, prev } = overrides.pop()!;
      if (prev) Object.defineProperty(target, key, prev);
      else Reflect.deleteProperty(target, key);
    }
  };
}
