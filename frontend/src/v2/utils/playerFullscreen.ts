// iPhone exposes no Fullscreen API on non-video elements, so a player's
// fullscreen control is inert there. We emulate just enough of the API to
// drive a fixed, viewport-filling stage.
//
// No nav-hiding counterpart is needed: players call useStageActive, which
// unmounts AppNav and BottomNav for the duration of the session.
const FULLSCREEN_STYLE = `
  [data-fullscreen-fallback] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100svh !important;
    z-index: 99999 !important;
    background: var(--r-color-canvas-bg) !important;
  }
`;

// Feature-detected rather than sniffed for iOS: iPad has the API behind the
// webkit prefix and iPhone has none at all, so sniffing would swap a working
// native implementation for this one on iPad. It also retires the fallback by
// itself if iPhone ever ships the real API.
function hasNativeElementFullscreen() {
  return (
    "requestFullscreen" in Element.prototype ||
    "webkitRequestFullscreen" in Element.prototype
  );
}

/**
 * Patches the Fullscreen API where the platform has none for elements.
 *
 * Returns: a disposer that exits the emulated fullscreen and restores every
 * patched property. A no-op wherever the native API exists.
 */
export function installFullscreenFallback(): () => void {
  if (hasNativeElementFullscreen()) {
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

    el.setAttribute("data-fullscreen-fallback", "");
    fullscreenElement = el;
    dispatchChange(el);
    return Promise.resolve();
  };

  const exit = () => {
    const el = fullscreenElement;
    if (!el) return Promise.resolve();
    el.removeAttribute("data-fullscreen-fallback");
    fullscreenElement = null;
    dispatchChange(el);
    return Promise.resolve();
  };

  override(document, "fullscreenEnabled", { get: () => true });
  override(document, "fullscreenElement", { get: () => fullscreenElement });
  // The deprecated alias for "is the document fullscreen". Support probes
  // (vueuse's useFullscreen among them) read it to decide the API is usable,
  // so a polyfill that omits it reads as unsupported and silently no-ops.
  override(document, "fullScreen", { get: () => fullscreenElement !== null });
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
