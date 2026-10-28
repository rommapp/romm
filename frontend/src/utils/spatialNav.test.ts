import { describe, expect, it } from "vitest";
import { pickSpatialTarget, spatialScore } from "./spatialNav";

function box(left: number, top: number, width = 40, height = 40) {
  return { left, top, right: left + width, bottom: top + height };
}

describe("spatialScore", () => {
  const from = box(100, 100);

  it("rejects candidates behind or beside the move", () => {
    expect(spatialScore(from, box(100, 20), "down")).toBeNull();
    expect(spatialScore(from, box(200, 100), "down")).toBeNull();
    expect(spatialScore(from, box(100, 200), "up")).toBeNull();
    expect(spatialScore(from, box(20, 100), "right")).toBeNull();
  });

  it("ranks diagonal candidates after those inside the cone", () => {
    const diagonal = spatialScore(from, box(160, 300), "right")!;
    const farAhead = spatialScore(from, box(900, 160), "right")!;
    expect(diagonal).toBeGreaterThan(farAhead);
  });

  it("accepts candidates past the edge in each direction", () => {
    expect(spatialScore(from, box(100, 200), "down")).not.toBeNull();
    expect(spatialScore(from, box(100, 20), "up")).not.toBeNull();
    expect(spatialScore(from, box(200, 100), "right")).not.toBeNull();
    expect(spatialScore(from, box(20, 100), "left")).not.toBeNull();
  });
});

describe("pickSpatialTarget", () => {
  it("prefers the control straight ahead over a nearer one off to the side", () => {
    const from = box(100, 300);
    const ahead = { item: "ahead", box: box(90, 160, 200, 40) };
    const aside = { item: "aside", box: box(190, 200) };

    expect(pickSpatialTarget(from, [aside, ahead], "up")).toBe("ahead");
  });

  it("picks the nearest of several aligned controls", () => {
    const from = box(100, 100);
    const near = { item: "near", box: box(100, 160) };
    const far = { item: "far", box: box(100, 400) };

    expect(pickSpatialTarget(from, [far, near], "down")).toBe("near");
  });

  it("falls back to a diagonal when nothing lies straight ahead", () => {
    const from = box(300, 300);
    const topBar = { item: "top-bar", box: box(0, 250) };

    expect(pickSpatialTarget(from, [topBar], "up")).toBe("top-bar");
  });

  it("returns null when nothing lies in the direction", () => {
    expect(
      pickSpatialTarget(box(0, 0), [{ item: "x", box: box(0, 100) }], "up"),
    ).toBeNull();
  });
});
