// iPhone exposes no Fullscreen API on non-video elements, so a player's
// fullscreen control is inert there without this.
const FALLBACK_ATTR = "data-fullscreen-fallback";

const FULLSCREEN_STYLE = `
  [${FALLBACK_ATTR}] {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100svh !important;
    z-index: 99999 !important;
    background: var(--r-color-canvas-bg, black) !important;
  }
`;

// Feature-detected, not sniffed: iPad has the API behind the webkit prefix, so
// sniffing iOS would swap a working native implementation for this one.
function hasElementFullscreen() {
  return (
    "requestFullscreen" in HTMLElement.prototype ||
    "webkitRequestFullscreen" in HTMLElement.prototype
  );
}

/**
 * Patches the Fullscreen API where the platform has none for elements.
 *
 * Returns: a disposer that exits the emulated fullscreen and restores every
 * patched property. A no-op wherever the native API exists.
 */
export function installFullscreenFallback(): () => void {
  if (hasElementFullscreen()) {
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

  // The real API exits when its element leaves the document, so watch for that
  // rather than leave callers holding a detached fullscreenElement.
  const detachWatcher = new MutationObserver(() => {
    if (fullscreenElement && !fullscreenElement.isConnected) void exit();
  });

  const enter = (el: HTMLElement) => {
    if (fullscreenElement === el) return Promise.resolve();
    if (fullscreenElement) void exit();

    el.setAttribute(FALLBACK_ATTR, "");
    fullscreenElement = el;
    detachWatcher.observe(document, { childList: true, subtree: true });
    dispatchChange(el);
    return Promise.resolve();
  };

  const exit = () => {
    const el = fullscreenElement;
    if (!el) return Promise.resolve();
    el.removeAttribute(FALLBACK_ATTR);
    fullscreenElement = null;
    detachWatcher.disconnect();
    dispatchChange(el);
    return Promise.resolve();
  };

  override(document, "fullscreenEnabled", { get: () => true });
  override(document, "fullscreenElement", { get: () => fullscreenElement });
  // Support probes read this deprecated alias to decide the API is usable, so
  // omitting it makes the polyfill read as unsupported.
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
    detachWatcher.disconnect();
    styleEl.remove();
    while (overrides.length) {
      const { target, key, prev } = overrides.pop()!;
      if (prev) Object.defineProperty(target, key, prev);
      else Reflect.deleteProperty(target, key);
    }
  };
}
