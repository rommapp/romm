import { describe, expect, it } from "vitest";
import { createPico8Pacer } from "./pico8Pacer";

// 30 fps carts get a 33.33ms budget per emulated frame.
const FRAME = 1000 / 30;

describe("createPico8Pacer", () => {
  it("runs one frame on the first tick so the cart paints immediately", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(1000);

    expect(pacer.tick(1000)).toBe(1);
  });

  // Individual ticks jitter between 0 and 2 on exact frame boundaries, since
  // 1000/30 is not representable; what matters is that the total does not drift.
  it("emulates one frame per display frame without drifting", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);

    let total = 0;
    for (let tick = 0; tick <= 300; tick += 1)
      total += pacer.tick(tick * FRAME);

    // 301 ticks, so 301 frames give or take whatever partial frame is still
    // banked. A pacer that drifted would be out by far more than one.
    expect(total).toBeGreaterThanOrEqual(300);
    expect(total).toBeLessThanOrEqual(301);
  });

  it("skips a frame when the display is faster than the cart", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);
    pacer.tick(0);

    // 60Hz display, 30 fps cart: every other tick has nothing to do.
    expect(pacer.tick(FRAME / 2)).toBe(0);
    expect(pacer.tick(FRAME)).toBe(1);
  });

  it("catches up on a short stall", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);
    pacer.tick(0);

    expect(pacer.tick(FRAME * 2)).toBe(2);
  });

  it("caps catch-up so a long stall cannot run the cart at speed", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);
    pacer.tick(0);

    expect(pacer.tick(FRAME * 50)).toBe(3);
  });

  it("drops the debt a capped tick could not spend", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);
    pacer.tick(0);
    pacer.tick(FRAME * 50);

    // Without dropping it, the next ticks would stay pinned at the cap.
    expect(pacer.tick(FRAME * 51)).toBe(1);
  });

  it("ignores a timestamp that goes backwards", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(1000);
    pacer.tick(1000);

    expect(pacer.tick(500)).toBe(0);
  });

  it("honours a 60 fps cart", () => {
    const pacer = createPico8Pacer(60);
    pacer.reset(0);
    pacer.tick(0);

    expect(pacer.tick(1000 / 60)).toBe(1);
    expect(pacer.tick(1000 / 60 + 1000 / 120)).toBe(0);
  });

  it("re-anchors on reset so a replay does not inherit the old clock", () => {
    const pacer = createPico8Pacer(30);
    pacer.reset(0);
    pacer.tick(0);
    pacer.tick(FRAME);

    pacer.reset(9_000_000);
    expect(pacer.tick(9_000_000)).toBe(1);
  });
});
