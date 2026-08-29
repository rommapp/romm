import { describe, expect, it } from "vitest";
import { effectScope } from "vue";
import { useIsAlive } from "./index";

describe("useIsAlive", () => {
  it("starts alive and flips on scope disposal", () => {
    const scope = effectScope();
    const alive = scope.run(() => useIsAlive())!;

    expect(alive.value).toBe(true);
    scope.stop();
    expect(alive.value).toBe(false);
  });

  it("keeps sibling scopes independent", () => {
    const a = effectScope();
    const b = effectScope();
    const aliveA = a.run(() => useIsAlive())!;
    const aliveB = b.run(() => useIsAlive())!;

    a.stop();
    expect(aliveA.value).toBe(false);
    expect(aliveB.value).toBe(true);
  });
});
