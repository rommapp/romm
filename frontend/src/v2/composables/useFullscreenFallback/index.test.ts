import { afterEach, describe, expect, it } from "vitest";
import { effectScope, type EffectScope } from "vue";
import { useFullscreenFallback } from "./index";

// happy-dom ships no Fullscreen API, so the fallback installs by default here.
const scopes: EffectScope[] = [];

function runInScope(fn: () => void): EffectScope {
  const scope = effectScope();
  scopes.push(scope);
  scope.run(fn);
  return scope;
}

// Stopped here rather than inline so a failed assertion cannot leave the
// document patched for the next test.
afterEach(() => {
  while (scopes.length) scopes.pop()?.stop();
});

describe("useFullscreenFallback", () => {
  it("removes the fallback when the scope is disposed", () => {
    const scope = runInScope(() => useFullscreenFallback());
    expect("requestFullscreen" in HTMLElement.prototype).toBe(true);

    scope.stop();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(false);
  });

  it("keeps the fallback while another consumer still holds it", () => {
    const first = runInScope(() => useFullscreenFallback());
    runInScope(() => useFullscreenFallback());

    first.stop();

    expect("requestFullscreen" in HTMLElement.prototype).toBe(true);
  });
});
