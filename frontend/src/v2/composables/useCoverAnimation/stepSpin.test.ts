import { describe, expect, it } from "vitest";
import { SPIN_CONFIG, stepSpin } from "./index";

describe("stepSpin", () => {
  it("accelerates while hovered", () => {
    const r = stepSpin({ angle: 0, velocity: 0 }, 0.1, true);
    expect(r.velocity).toBeCloseTo(SPIN_CONFIG.accel * 0.1); // 250
    expect(r.angle).toBeGreaterThan(0);
  });

  it("clamps velocity at maxSpeed", () => {
    const r = stepSpin({ angle: 0, velocity: SPIN_CONFIG.maxSpeed }, 0.1, true);
    expect(r.velocity).toBe(SPIN_CONFIG.maxSpeed);
  });

  it("decelerates when not hovered and never goes negative", () => {
    const slowing = stepSpin({ angle: 0, velocity: 300 }, 0.1, false);
    expect(slowing.velocity).toBeCloseTo(300 - SPIN_CONFIG.decel * 0.1); // 150
    const floored = stepSpin({ angle: 0, velocity: 50 }, 1, false);
    expect(floored.velocity).toBe(0);
  });

  it("wraps the angle at 360°", () => {
    const r = stepSpin({ angle: 359, velocity: 360 }, 1, false);
    expect(r.angle).toBeGreaterThanOrEqual(0);
    expect(r.angle).toBeLessThan(360);
  });

  it("a stopped, un-hovered disc stays put", () => {
    const r = stepSpin({ angle: 42, velocity: 0 }, 0.1, false);
    expect(r.velocity).toBe(0);
    expect(r.angle).toBe(42);
  });
});
