import { afterEach, describe, expect, it } from "vitest";
import { effectScope, ref, type EffectScope } from "vue";
import { usePlayerFullscreen } from "./index";

// happy-dom ships no Fullscreen API, so the fallback installs by default here
// and a test opts into the native path by defining the method itself.
const NATIVE_KEYS = ["requestFullscreen", "webkitRequestFullscreen"] as const;

let scope: EffectScope | null = null;

// Stopped in afterEach rather than inline: a failed assertion inside
// scope.run() would otherwise leave the fallback patched for the next test.
function runInScope<T>(fn: () => T): T {
  scope = effectScope();
  return scope.run(fn) as T;
}

afterEach(() => {
  scope?.stop();
  scope = null;
  NATIVE_KEYS.forEach((key) => Reflect.deleteProperty(Element.prototype, key));
  document.body.innerHTML = "";
});

function mountStage() {
  const el = document.createElement("div");
  document.body.appendChild(el);
  return ref<HTMLElement | null>(el);
}

describe("usePlayerFullscreen", () => {
  it("installs the fallback so a stage can go fullscreen without the native API", async () => {
    const stage = mountStage();
    const { enter, isFullscreen } = runInScope(() =>
      usePlayerFullscreen(stage),
    );

    await enter();

    expect(stage.value?.hasAttribute("data-fullscreen-fallback")).toBe(true);
    expect(isFullscreen.value).toBe(true);
  });

  it("exits back out of the fallback", async () => {
    const stage = mountStage();
    const { enter, exit, isFullscreen } = runInScope(() =>
      usePlayerFullscreen(stage),
    );

    await enter();
    await exit();

    expect(stage.value?.hasAttribute("data-fullscreen-fallback")).toBe(false);
    expect(isFullscreen.value).toBe(false);
  });

  it("removes the fallback when the scope is disposed", () => {
    runInScope(() => usePlayerFullscreen());
    expect("requestFullscreen" in HTMLElement.prototype).toBe(true);

    scope?.stop();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(false);
  });

  it("stands aside where the native API exists", () => {
    const native = () => Promise.resolve();
    Object.defineProperty(Element.prototype, "requestFullscreen", {
      value: native,
      configurable: true,
      writable: true,
    });

    runInScope(() => usePlayerFullscreen(mountStage()));

    expect(Element.prototype.requestFullscreen).toBe(native);
  });

  it("swallows a denied request instead of rejecting", async () => {
    Object.defineProperty(Element.prototype, "requestFullscreen", {
      value: () => Promise.reject(new Error("denied")),
      configurable: true,
      writable: true,
    });
    const { enter } = runInScope(() => usePlayerFullscreen(mountStage()));

    await expect(enter()).resolves.toBeUndefined();
  });
});
