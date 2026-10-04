import { describe, expect, it, vi } from "vitest";
import { computed, effectScope, ref, watch } from "vue";
import { useAnimatedNumber } from "./index";

// Reduced motion lands on the value in one step, which is what makes the
// state machine readable without chasing frames.
const reduced = ref(true);
vi.mock("@/v2/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: computed(() => reduced.value) }),
}));

describe("useAnimatedNumber", () => {
  it("shows the value it is given", () => {
    const source = ref<number | null>(42);

    const display = useAnimatedNumber(() => source.value);

    expect(display.value).toBe(42);
  });

  it("lands exactly on each new value", async () => {
    const source = ref<number | null>(3);
    const display = useAnimatedNumber(() => source.value);

    source.value = 88;
    await Promise.resolve();

    expect(display.value).toBe(88);
  });

  it("paints a missing value as nothing to roll to", async () => {
    const source = ref<number | null>(7);
    const display = useAnimatedNumber(() => source.value);

    source.value = null;
    await Promise.resolve();

    expect(display.value).toBeNull();
  });

  it("rolls through the numbers on the way when motion is allowed", async () => {
    reduced.value = false;
    const source = ref<number | null>(0);
    const scope = effectScope();
    const seen: (string | number | null)[] = [];
    let display!: ReturnType<typeof useAnimatedNumber>;
    scope.run(() => {
      display = useAnimatedNumber(() => source.value, { duration: 60 });
    });

    source.value = 100;
    await new Promise((resolve) => setTimeout(resolve, 20));
    seen.push(display.value);
    await new Promise((resolve) => setTimeout(resolve, 80));

    // Caught mid-roll it sits between the two, and it finishes on the target.
    expect(seen[0]).toBeGreaterThan(0);
    expect(seen[0]).toBeLessThan(100);
    expect(display.value).toBe(100);
    scope.stop();
    reduced.value = true;
  });

  it("picks up where a remembered count left off after a remount", async () => {
    reduced.value = false;
    const source = ref<number | null>(573);
    const first = effectScope();
    first.run(() =>
      useAnimatedNumber(() => source.value, { rememberAs: () => "remount" }),
    );
    first.stop();

    const second = effectScope();
    let display!: ReturnType<typeof useAnimatedNumber>;
    second.run(() => {
      display = useAnimatedNumber(() => source.value, {
        rememberAs: () => "remount",
      });
    });

    // Already landed before, so it paints the value without rolling from 0.
    expect(display.value).toBe(573);
    second.stop();
    reduced.value = true;
  });

  it("rolls a remembered count from its last value when it changed", async () => {
    reduced.value = false;
    const source = ref<number | null>(10);
    const first = effectScope();
    first.run(() =>
      useAnimatedNumber(() => source.value, { rememberAs: () => "changed" }),
    );
    first.stop();

    source.value = 20;
    const second = effectScope();
    const seen: number[] = [];
    let display!: ReturnType<typeof useAnimatedNumber>;
    second.run(() => {
      display = useAnimatedNumber(() => source.value, {
        duration: 200,
        rememberAs: () => "changed",
      });
      watch(display, (value) => seen.push(Number(value)), { flush: "sync" });
    });
    await vi.waitFor(() => expect(display.value).toBe(20));

    expect(Math.min(...seen)).toBeGreaterThanOrEqual(10);
    second.stop();
    reduced.value = true;
  });

  it("remembers a count reused under a new key with an equal value", async () => {
    reduced.value = false;
    const source = ref<number | null>(5);
    const key = ref("equal-a");
    const first = effectScope();
    first.run(() =>
      useAnimatedNumber(() => source.value, { rememberAs: () => key.value }),
    );
    key.value = "equal-b";
    await Promise.resolve();
    first.stop();

    const second = effectScope();
    let display!: ReturnType<typeof useAnimatedNumber>;
    second.run(() => {
      display = useAnimatedNumber(() => source.value, {
        rememberAs: () => "equal-b",
      });
    });

    expect(display.value).toBe(5);
    second.stop();
    reduced.value = true;
  });
});
