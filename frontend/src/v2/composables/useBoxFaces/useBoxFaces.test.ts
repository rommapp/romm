import { describe, expect, it } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { computeBoxFaces, type BoxFacesRom } from "./index";

const RES = "/assets/romm/resources";

// Minimal rom factory — computeBoxFaces only reads the cover chain and the
// two ss_metadata path fields. Single cast scoped to the test.
function rom(over: Partial<SimpleRom>): BoxFacesRom {
  const base: Partial<SimpleRom> = {
    path_cover_large: null,
    path_cover_small: null,
    ss_metadata: null,
  };
  return { ...base, ...over } as BoxFacesRom;
}

describe("computeBoxFaces", () => {
  it("is incomplete when the rom only has a cover", () => {
    const faces = computeBoxFaces(
      rom({ path_cover_large: "roms/1/1/cover/l.png" }),
      false,
    );
    expect(faces.front).toBe("roms/1/1/cover/l.png");
    expect(faces.back).toBeNull();
    expect(faces.spine).toBeNull();
    expect(faces.complete).toBe(false);
  });

  it("resolves all three faces and reports complete", () => {
    const faces = computeBoxFaces(
      rom({
        path_cover_large: "roms/1/1/cover/l.png",
        ss_metadata: {
          box2d_back_path: "roms/1/1/box2d_back/box2d_back.png",
          box2d_side_path: "roms/1/1/box2d_side/box2d_side.png",
        },
      }),
      false,
    );
    expect(faces.front).toBe("roms/1/1/cover/l.png");
    expect(faces.back).toBe(`${RES}/roms/1/1/box2d_back/box2d_back.png`);
    expect(faces.spine).toBe(`${RES}/roms/1/1/box2d_side/box2d_side.png`);
    expect(faces.complete).toBe(true);
  });

  it("is incomplete when the spine is missing", () => {
    const faces = computeBoxFaces(
      rom({
        path_cover_large: "roms/1/1/cover/l.png",
        ss_metadata: { box2d_back_path: "roms/1/1/box2d_back/box2d_back.png" },
      }),
      false,
    );
    expect(faces.spine).toBeNull();
    expect(faces.complete).toBe(false);
  });

  it("rewrites the front cover to webp when supported, leaving faces as png", () => {
    const faces = computeBoxFaces(
      rom({
        path_cover_large: "roms/1/1/cover/l.png",
        ss_metadata: {
          box2d_back_path: "roms/1/1/box2d_back/box2d_back.png",
          box2d_side_path: "roms/1/1/box2d_side/box2d_side.png",
        },
      }),
      true,
    );
    expect(faces.front).toBe("roms/1/1/cover/l.webp");
    expect(faces.back).toBe(`${RES}/roms/1/1/box2d_back/box2d_back.png`);
  });

  it("falls back to the small cover when the large one is absent", () => {
    const faces = computeBoxFaces(
      rom({ path_cover_small: "roms/1/1/cover/s.png" }),
      false,
    );
    expect(faces.front).toBe("roms/1/1/cover/s.png");
  });
});
