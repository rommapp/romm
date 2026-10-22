// Checks RomM's cover generator after patches/30-frontend-cover-art.mjs: a theme's CSS variables
// choose its artwork or recolor RomM's, and RomM's own art is used without them.
import { afterEach, describe, expect, it, vi } from "vitest";
import { colorCoverArt } from "@/v2/tokens";

async function freshCovers(vars: Record<string, string>) {
  for (const [name, value] of Object.entries(vars)) {
    document.documentElement.style.setProperty(name, value);
  }
  vi.resetModules();
  return import("@/v2/utils/covers");
}

describe("themed placeholder covers", () => {
  afterEach(() => {
    document.documentElement.removeAttribute("style");
  });

  it("picks one of the theme's artworks per game, the same each time", async () => {
    const { coverPlaceholderArt } = await freshCovers({
      "--themeable-cover-missing":
        "/themes/neon/covers/missing-1.svg /themes/neon/covers/missing-2.svg",
      "--themeable-cover-unmatched": "/themes/neon/covers/unmatched-1.svg",
    });
    const art = coverPlaceholderArt("Chrono Trigger", true);
    expect(art).toMatch(/^\/themes\/neon\/covers\/missing-[12]\.svg$/);
    expect(coverPlaceholderArt("Chrono Trigger", true)).toBe(art);
    expect(coverPlaceholderArt("Chrono Trigger", false)).toBe(
      "/themes/neon/covers/unmatched-1.svg",
    );
  });

  it("draws RomM's art in the theme's colors when it has no artwork", async () => {
    const { coverPlaceholderArt } = await freshCovers({
      "--themeable-cover-base": "#112233",
    });
    const svg = decodeURIComponent(coverPlaceholderArt("Metroid", true));
    expect(svg).toContain("#112233");
    expect(svg).toContain(colorCoverArt.warm);
  });

  it("keeps RomM's own art without a theme", async () => {
    const { coverPlaceholderArt } = await freshCovers({});
    const svg = decodeURIComponent(coverPlaceholderArt("Metroid", true));
    expect(svg).toContain(colorCoverArt.base);
  });
});
