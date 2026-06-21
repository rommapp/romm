import { describe, expect, it } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import {
  altArtPath,
  computeCoverArt,
  coverRatio,
  isBoxartStyle,
  naturalCoverRatio,
} from "./index";

const RES = "/assets/romm/resources";

// Minimal rom factory — the pure helpers only read the cover-related
// fields, so we default the rest and let callers override. Single cast
// from Partial (a supertype) to SimpleRom, scoped to the test.
function rom(over: Partial<SimpleRom>): SimpleRom {
  const base: Partial<SimpleRom> = {
    path_cover_large: null,
    path_cover_small: null,
    url_cover: null,
    path_video: null,
    platform_slug: "snes",
    ss_metadata: null,
    gamelist_metadata: null,
  };
  return { ...base, ...over } as SimpleRom;
}

describe("isBoxartStyle", () => {
  it("accepts the four known styles", () => {
    expect(isBoxartStyle("cover_path")).toBe(true);
    expect(isBoxartStyle("box3d_path")).toBe(true);
    expect(isBoxartStyle("physical_path")).toBe(true);
    expect(isBoxartStyle("miximage_path")).toBe(true);
  });
  it("rejects anything else", () => {
    expect(isBoxartStyle("nope")).toBe(false);
    expect(isBoxartStyle(undefined)).toBe(false);
    expect(isBoxartStyle(null)).toBe(false);
  });
});

describe("coverRatio", () => {
  it("matches v1 getAspectRatio for every style", () => {
    expect(coverRatio("cover_path")).toBeCloseTo(2 / 3);
    expect(coverRatio("box3d_path")).toBeCloseTo(3 / 4);
    expect(coverRatio("physical_path")).toBe(1);
    expect(coverRatio("miximage_path")).toBe(1);
  });
});

describe("naturalCoverRatio", () => {
  it("uses the rom's recorded dimensions for the default box-art style", () => {
    const r = rom({ cover_width: 300, cover_height: 400 });
    expect(naturalCoverRatio(r, "cover_path")).toBeCloseTo(300 / 400);
  });
  it("falls back to the canonical box-art ratio when dimensions are missing", () => {
    expect(naturalCoverRatio(rom({}), "cover_path")).toBeCloseTo(2 / 3);
    expect(
      naturalCoverRatio(rom({ cover_width: 0, cover_height: 0 }), "cover_path"),
    ).toBeCloseTo(2 / 3);
    expect(
      naturalCoverRatio(
        rom({ cover_width: 300, cover_height: null }),
        "cover_path",
      ),
    ).toBeCloseTo(2 / 3);
  });
  it("ignores recorded dimensions for alt-art styles (fixed shapes)", () => {
    const r = rom({ cover_width: 300, cover_height: 400 });
    expect(naturalCoverRatio(r, "box3d_path")).toBeCloseTo(3 / 4);
    expect(naturalCoverRatio(r, "physical_path")).toBe(1);
    expect(naturalCoverRatio(r, "miximage_path")).toBe(1);
  });
});

describe("computeCoverArt natural ratio", () => {
  it("threads the rom's natural ratio into the descriptor for cover_path", () => {
    const desc = computeCoverArt(
      rom({ path_cover_large: "c.png", cover_width: 200, cover_height: 300 }),
      "cover_path",
      { resourcesPath: RES, supportsWebp: false },
    );
    expect(desc.ratio).toBeCloseTo(200 / 300);
  });
});

describe("altArtPath", () => {
  it("returns null for cover_path", () => {
    expect(
      altArtPath(rom({ ss_metadata: { box3d_path: "x.png" } }), "cover_path"),
    ).toBeNull();
  });
  it("prefers ss_metadata over gamelist_metadata", () => {
    const r = rom({
      ss_metadata: { box3d_path: "ss.png" },
      gamelist_metadata: { box3d_path: "gl.png" },
    });
    expect(altArtPath(r, "box3d_path")).toBe("ss.png");
  });
  it("falls back to gamelist_metadata", () => {
    const r = rom({ gamelist_metadata: { physical_path: "gl.png" } });
    expect(altArtPath(r, "physical_path")).toBe("gl.png");
  });
  it("returns null when neither provider has the asset", () => {
    expect(altArtPath(rom({}), "miximage_path")).toBeNull();
  });
});

describe("computeCoverArt — cover_path", () => {
  it("uses the local large cover, object-fit cover, 2/3 ratio", () => {
    const r = rom({
      path_cover_large: "covers/large.png",
      path_cover_small: "covers/small.png",
    });
    const d = computeCoverArt(r, "cover_path", {
      resourcesPath: RES,
      supportsWebp: false,
    });
    expect(d.coverUrl).toBe("covers/large.png");
    expect(d.objectFit).toBe("cover");
    expect(d.ratio).toBeCloseTo(2 / 3);
    expect(d.isAltArt).toBe(false);
    expect(d.animateCD).toBe(false);
    expect(d.videoUrl).toBeNull();
  });
  it("falls back to the small cover when large is absent", () => {
    const d = computeCoverArt(
      rom({ path_cover_small: "covers/small.png" }),
      "cover_path",
      {
        resourcesPath: RES,
        supportsWebp: false,
      },
    );
    expect(d.coverUrl).toBe("covers/small.png");
  });
  it("rewrites the local cover extension to webp when supported", () => {
    const d = computeCoverArt(
      rom({ path_cover_large: "covers/large.jpg" }),
      "cover_path",
      {
        resourcesPath: RES,
        supportsWebp: true,
      },
    );
    expect(d.coverUrl).toBe("covers/large.webp");
  });
  it("exposes url_cover as the fallback and flags no artwork when empty", () => {
    expect(
      computeCoverArt(rom({ url_cover: "https://x/c.png" }), "cover_path", {
        resourcesPath: RES,
        supportsWebp: false,
      }).fallbackUrl,
    ).toBe("https://x/c.png");
    expect(
      computeCoverArt(rom({}), "cover_path", {
        resourcesPath: RES,
        supportsWebp: false,
      }).hasArtwork,
    ).toBe(false);
  });
});

describe("computeCoverArt — box3d_path", () => {
  it("prefixes the alt path, uses contain + 3/4, no webp rewrite", () => {
    const r = rom({
      ss_metadata: { box3d_path: "ss/box3d.png" },
      path_cover_large: "covers/l.png",
    });
    const d = computeCoverArt(r, "box3d_path", {
      resourcesPath: RES,
      supportsWebp: true,
    });
    expect(d.coverUrl).toBe(`${RES}/ss/box3d.png`);
    expect(d.objectFit).toBe("contain");
    expect(d.ratio).toBeCloseTo(3 / 4);
    expect(d.isAltArt).toBe(true);
  });
  it("letterboxes the local cover when the alt art is missing (style ratio still applies)", () => {
    const d = computeCoverArt(
      rom({ path_cover_large: "covers/l.png" }),
      "box3d_path",
      {
        resourcesPath: RES,
        supportsWebp: false,
      },
    );
    expect(d.coverUrl).toBe("covers/l.png");
    expect(d.isAltArt).toBe(false);
    expect(d.objectFit).toBe("contain");
    expect(d.ratio).toBeCloseTo(3 / 4);
  });
});

describe("computeCoverArt — physical_path animations", () => {
  it("spins on CD-based platforms", () => {
    const r = rom({
      platform_slug: "psx",
      ss_metadata: { physical_path: "disc.png" },
    });
    const d = computeCoverArt(r, "physical_path", {
      resourcesPath: RES,
      supportsWebp: false,
    });
    expect(d.animateCD).toBe(true);
    expect(d.animateCartridge).toBe(false);
  });
  it("drops a cartridge on non-CD platforms", () => {
    const r = rom({
      platform_slug: "snes",
      ss_metadata: { physical_path: "cart.png" },
    });
    const d = computeCoverArt(r, "physical_path", {
      resourcesPath: RES,
      supportsWebp: false,
    });
    expect(d.animateCD).toBe(false);
    expect(d.animateCartridge).toBe(true);
  });
  it("never animates when the physical art is missing", () => {
    const d = computeCoverArt(rom({ platform_slug: "psx" }), "physical_path", {
      resourcesPath: RES,
      supportsWebp: false,
    });
    expect(d.animateCD).toBe(false);
    expect(d.animateCartridge).toBe(false);
  });
});

describe("computeCoverArt — miximage_path video", () => {
  it("resolves the hover video when path_video is present", () => {
    const r = rom({
      ss_metadata: { miximage_path: "mix.png" },
      path_video: "videos/clip.mp4",
    });
    const d = computeCoverArt(r, "miximage_path", {
      resourcesPath: RES,
      supportsWebp: false,
    });
    expect(d.videoUrl).toBe(`${RES}/videos/clip.mp4`);
  });
  it("has no video when path_video is absent", () => {
    const d = computeCoverArt(
      rom({ ss_metadata: { miximage_path: "mix.png" } }),
      "miximage_path",
      {
        resourcesPath: RES,
        supportsWebp: false,
      },
    );
    expect(d.videoUrl).toBeNull();
  });
});

describe("computeCoverArt — explicit coverSrc override", () => {
  it("treats an empty-string coverSrc as no override (resolves the rom cover + keeps the url_cover fallback)", () => {
    const d = computeCoverArt(
      rom({ path_cover_large: "covers/l.png", url_cover: "https://x/c.png" }),
      "cover_path",
      { resourcesPath: RES, supportsWebp: false, coverSrc: "" },
    );
    expect(d.coverUrl).toBe("covers/l.png");
    expect(d.fallbackUrl).toBe("https://x/c.png");
  });

  it("wins over the resolution chain and disables alt-art / webp", () => {
    const r = rom({
      ss_metadata: { box3d_path: "ss/box3d.png" },
      path_cover_large: "covers/l.jpg",
    });
    const d = computeCoverArt(r, "box3d_path", {
      resourcesPath: RES,
      supportsWebp: true,
      coverSrc: "blob:preview",
    });
    expect(d.coverUrl).toBe("blob:preview");
    expect(d.isAltArt).toBe(false);
    expect(d.fallbackUrl).toBeNull();
  });
});
