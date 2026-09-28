import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { installFullscreenFallback } from "./playerFullscreen";

// happy-dom ships no Fullscreen API, so the fallback installs by default here
// and a test opts into the native path by defining the method itself.
const NATIVE_KEYS = ["requestFullscreen", "webkitRequestFullscreen"] as const;

let dispose: (() => void) | undefined;

function defineNative(key: (typeof NATIVE_KEYS)[number], value: unknown) {
  Object.defineProperty(Element.prototype, key, {
    value,
    configurable: true,
    writable: true,
  });
}

beforeEach(() => {
  NATIVE_KEYS.forEach((key) => Reflect.deleteProperty(Element.prototype, key));
});

// Disposed here rather than inline so a failed assertion cannot leave the
// document patched for the next test.
afterEach(() => {
  dispose?.();
  dispose = undefined;
  NATIVE_KEYS.forEach((key) => Reflect.deleteProperty(Element.prototype, key));
  document.body.innerHTML = "";
});

// The deprecated alias the fallback also defines; lib.dom has no type for it.
function legacyFullScreen(): unknown {
  return Reflect.get(document, "fullScreen");
}

function mountStage() {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return el;
}

describe("installFullscreenFallback", () => {
  it("stands aside where the native API exists", () => {
    defineNative("requestFullscreen", () => Promise.resolve());
    const before = HTMLElement.prototype.requestFullscreen;

    dispose = installFullscreenFallback();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
  });

  it("stands aside where only the webkit-prefixed API exists (iPad)", () => {
    defineNative("webkitRequestFullscreen", () => undefined);
    const before = HTMLElement.prototype.requestFullscreen;

    dispose = installFullscreenFallback();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
  });

  it("reports fullscreen as available once installed", () => {
    dispose = installFullscreenFallback();

    expect(document.fullscreenEnabled).toBe(true);
    expect(document.fullscreenElement).toBeNull();
    expect(legacyFullScreen()).toBe(false);
  });

  it("marks the element and fires fullscreenchange on enter", async () => {
    dispose = installFullscreenFallback();
    const el = mountStage();

    let changes = 0;
    document.addEventListener("fullscreenchange", () => changes++);

    await el.requestFullscreen();

    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(true);
    expect(document.fullscreenElement).toBe(el);
    expect(legacyFullScreen()).toBe(true);
    expect(changes).toBe(1);
  });

  it("clears the element on exit", async () => {
    dispose = installFullscreenFallback();
    const el = mountStage();

    await el.requestFullscreen();
    await document.exitFullscreen();

    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(false);
    expect(document.fullscreenElement).toBeNull();
    expect(legacyFullScreen()).toBe(false);
  });

  it("exits when the fullscreen element leaves the document", async () => {
    dispose = installFullscreenFallback();
    const el = mountStage();
    await el.requestFullscreen();

    const changed = new Promise<void>((resolve) =>
      document.addEventListener("fullscreenchange", () => resolve(), {
        once: true,
      }),
    );
    el.remove();
    await changed;

    expect(document.fullscreenElement).toBeNull();
    expect(legacyFullScreen()).toBe(false);
  });

  it("restores the patched API and removes its stylesheet on dispose", async () => {
    const styleCount = document.head.querySelectorAll("style").length;

    const install = installFullscreenFallback();
    const el = mountStage();
    await el.requestFullscreen();
    install();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(false);
    expect(document.head.querySelectorAll("style")).toHaveLength(styleCount);
    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(false);
  });
});
