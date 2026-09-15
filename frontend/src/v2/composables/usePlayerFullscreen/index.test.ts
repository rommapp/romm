import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref, type EffectScope } from "vue";
import { useFullscreenFallback, usePlayerFullscreen } from "./index";

// happy-dom ships no Fullscreen API, so the fallback installs by default here.
// The util's own spec covers its behaviour; this covers the composable's.
const scopes: EffectScope[] = [];

function runInScope<T>(fn: () => T): { value: T; scope: EffectScope } {
  const scope = effectScope();
  scopes.push(scope);
  return { value: scope.run(fn) as T, scope };
}

// Stopped here rather than inline so a failed assertion cannot leave the
// document patched for the next test.
afterEach(() => {
  while (scopes.length) scopes.pop()?.stop();
  Reflect.deleteProperty(Element.prototype, "requestFullscreen");
  document.body.innerHTML = "";
});

describe("useFullscreenFallback", () => {
  it("removes the fallback when the scope is disposed", () => {
    const { scope } = runInScope(() => useFullscreenFallback());
    expect("requestFullscreen" in HTMLElement.prototype).toBe(true);

    scope.stop();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(false);
  });

  it("keeps the fallback while another consumer still holds it", () => {
    const first = runInScope(() => useFullscreenFallback());
    runInScope(() => useFullscreenFallback());

    first.scope.stop();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(true);
  });
});

describe("usePlayerFullscreen", () => {
  it("drives the stage through the installed fallback", async () => {
    const el = document.createElement("div");
    document.body.appendChild(el);
    const stage = ref<HTMLElement | null>(el);

    const { value } = runInScope(() => usePlayerFullscreen(stage));
    await value.enter();

    expect(value.isFullscreen.value).toBe(true);
    expect(el.hasAttribute("data-fullscreen-fallback")).toBe(true);
  });

  it("reports a failed exit, which leaves a dialog painted over", async () => {
    const el = document.createElement("div");
    document.body.appendChild(el);
    const { value } = runInScope(() =>
      usePlayerFullscreen(ref<HTMLElement | null>(el)),
    );
    await value.enter();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    Object.defineProperty(document, "exitFullscreen", {
      value: () => Promise.reject(new Error("denied")),
      configurable: true,
      writable: true,
    });

    await expect(value.exit()).resolves.toBeUndefined();

    expect(error).toHaveBeenCalledOnce();
    error.mockRestore();
  });

  it("swallows a denied request instead of rejecting", async () => {
    Object.defineProperty(Element.prototype, "requestFullscreen", {
      value: () => Promise.reject(new Error("denied")),
      configurable: true,
      writable: true,
    });
    const el = document.createElement("div");
    document.body.appendChild(el);

    const { value } = runInScope(() =>
      usePlayerFullscreen(ref<HTMLElement | null>(el)),
    );

    await expect(value.enter()).resolves.toBeUndefined();
  });
});
