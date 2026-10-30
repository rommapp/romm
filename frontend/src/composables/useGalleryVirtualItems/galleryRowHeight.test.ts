import { describe, expect, it } from "vitest";
import { galleryRowHeight } from "./index";

// Cover box height = round(cardWidth / ratio); chrome (label + gaps +
// bottom padding) = 41px added on top.
describe("galleryRowHeight", () => {
  it("defaults to the md box-art card (158 / (2/3) + 41 = 278)", () => {
    expect(galleryRowHeight()).toBe(278);
  });

  it("shrinks for the 3D box ratio (158 / 0.75 + 41 = 252)", () => {
    expect(galleryRowHeight(3 / 4)).toBe(252);
  });

  it("is shortest for square physical / miximage art (158 + 41 = 199)", () => {
    expect(galleryRowHeight(1)).toBe(199);
  });

  it("scales with a narrower card width (phones: 108 / (2/3) + 41 = 203)", () => {
    expect(galleryRowHeight(2 / 3, 108)).toBe(203);
  });
});
