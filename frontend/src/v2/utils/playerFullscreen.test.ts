import { afterEach, describe, expect, it } from "vitest";
import { installFullscreenFallback } from "./playerFullscreen";

// The fallback gates on Element.prototype, so the tests move the native
// methods on and off it rather than faking a user agent.
const NATIVE_KEYS = ["requestFullscreen", "webkitRequestFullscreen"] as const;
const nativeDescriptors = NATIVE_KEYS.map(
  (key) =>
    [key, Object.getOwnPropertyDescriptor(Element.prototype, key)] as const,
);

function withoutNativeFullscreen() {
  NATIVE_KEYS.forEach((key) => Reflect.deleteProperty(Element.prototype, key));
}

function withNativeFullscreen() {
  Object.defineProperty(Element.prototype, "requestFullscreen", {
    value: () => Promise.resolve(),
    configurable: true,
    writable: true,
  });
}

afterEach(() => {
  NATIVE_KEYS.forEach((key) => Reflect.deleteProperty(Element.prototype, key));
  nativeDescriptors.forEach(([key, descriptor]) => {
    if (descriptor) Object.defineProperty(Element.prototype, key, descriptor);
  });
  document.body.innerHTML = "";
});

describe("installFullscreenFallback", () => {
  it("stands aside where the native API exists", () => {
    withNativeFullscreen();
    const before = HTMLElement.prototype.requestFullscreen;

    const dispose = installFullscreenFallback();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
    dispose();
  });

  it("stands aside where only the webkit-prefixed API exists (iPad)", () => {
    withoutNativeFullscreen();
    Object.defineProperty(Element.prototype, "webkitRequestFullscreen", {
      value: () => undefined,
      configurable: true,
      writable: true,
    });
    const before = HTMLElement.prototype.requestFullscreen;

    const dispose = installFullscreenFallback();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
    dispose();
  });

  it("reports fullscreen as available once installed", () => {
    withoutNativeFullscreen();
    const dispose = installFullscreenFallback();

    expect(document.fullscreenEnabled).toBe(true);
    expect(document.fullscreenElement).toBeNull();

    dispose();
  });

  it("marks the element and fires fullscreenchange on enter", async () => {
    withoutNativeFullscreen();
    const dispose = installFullscreenFallback();
    const el = document.createElement("div");
    document.body.appendChild(el);

    let changes = 0;
    document.addEventListener("fullscreenchange", () => changes++);

    await el.requestFullscreen();

    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(true);
    expect(document.fullscreenElement).toBe(el);
    expect(changes).toBe(1);

    dispose();
  });

  it("clears the element on exit", async () => {
    withoutNativeFullscreen();
    const dispose = installFullscreenFallback();
    const el = document.createElement("div");
    document.body.appendChild(el);

    await el.requestFullscreen();
    await document.exitFullscreen();

    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(false);
    expect(document.fullscreenElement).toBeNull();

    dispose();
  });

  it("restores the patched API and removes its stylesheet on dispose", async () => {
    withoutNativeFullscreen();
    const styleCount = document.head.querySelectorAll("style").length;

    const dispose = installFullscreenFallback();
    const el = document.createElement("div");
    document.body.appendChild(el);
    await el.requestFullscreen();
    dispose();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(false);
    expect(document.head.querySelectorAll("style")).toHaveLength(styleCount);
    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(false);
  });
});
