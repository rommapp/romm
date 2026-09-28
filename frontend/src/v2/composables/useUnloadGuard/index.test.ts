import { afterEach, describe, expect, it } from "vitest";
import { effectScope, ref, type EffectScope } from "vue";
import { useUnloadGuard } from "./index";

let scope: EffectScope | null = null;

function arm(armed: Parameters<typeof useUnloadGuard>[0]) {
  scope = effectScope();
  scope.run(() => useUnloadGuard(armed));
}

function dispatchUnload(): BeforeUnloadEvent {
  const event = new Event("beforeunload", {
    cancelable: true,
  }) as BeforeUnloadEvent;
  window.dispatchEvent(event);
  return event;
}

afterEach(() => {
  scope?.stop();
  scope = null;
});

describe("useUnloadGuard", () => {
  it("blocks the unload while armed", () => {
    arm(true);

    expect(dispatchUnload().defaultPrevented).toBe(true);
  });

  it("lets the unload through while disarmed", () => {
    arm(false);

    expect(dispatchUnload().defaultPrevented).toBe(false);
  });

  it("re-reads the source on every unload", () => {
    const running = ref(false);
    arm(running);

    expect(dispatchUnload().defaultPrevented).toBe(false);

    running.value = true;

    expect(dispatchUnload().defaultPrevented).toBe(true);
  });

  it("stops guarding once the scope is disposed", () => {
    arm(true);
    scope?.stop();

    expect(dispatchUnload().defaultPrevented).toBe(false);
  });
});
