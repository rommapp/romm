import { describe, expect, it } from "vitest";
import {
  DEFAULT_PLATFORM_ICON,
  indexShippedPlatformIcons,
  listShippedPlatformIcons,
  platformIconSrc,
  resolveShippedPlatformIconUrl,
} from "./iconCache";

function asset(file: string): string {
  return `../../../../assets/platforms/${file}`;
}

describe("indexShippedPlatformIcons", () => {
  it("prefers svg over ico", () => {
    const paths = [asset("nes.svg"), asset("nes.ico")];

    const index = indexShippedPlatformIcons(paths);

    expect(index.get("nes")).toBe("nes.svg");
  });

  it("keeps ico-only slugs", () => {
    const paths = [asset("saturn.ico")];

    const index = indexShippedPlatformIcons(paths);

    expect(index.get("saturn")).toBe("saturn.ico");
  });

  it("keys by basename", () => {
    const paths = [asset("systematic/ps2.svg")];

    const index = indexShippedPlatformIcons(paths);

    expect(index.get("ps2")).toBe("ps2.svg");
  });
});

describe("resolveShippedPlatformIconUrl", () => {
  it("returns the public url for a shipped slug", () => {
    const index = indexShippedPlatformIcons([asset("saturn.ico")]);

    const url = resolveShippedPlatformIconUrl("saturn", index);

    expect(url).toBe("/assets/platforms/saturn.ico");
  });

  it("returns null when nothing shipped", () => {
    const index = indexShippedPlatformIcons([asset("dc.svg")]);

    const url = resolveShippedPlatformIconUrl("switch_mods", index);

    expect(url).toBeNull();
  });

  it("lowercases the lookup", () => {
    const index = indexShippedPlatformIcons([asset("dc.svg")]);

    const url = resolveShippedPlatformIconUrl("DC", index);

    expect(url).toBe("/assets/platforms/dc.svg");
  });
});

describe("platformIconSrc", () => {
  it("prefers an explicit src", () => {
    expect(platformIconSrc("dc", "nes", "/custom/icon.png")).toBe(
      "/custom/icon.png",
    );
  });

  it("uses the shipped slug before the filesystem slug", () => {
    expect(platformIconSrc("dc", "dreamcast")).toBe("/assets/platforms/dc.svg");
  });

  it("uses the filesystem slug when the canonical slug is unshipped", () => {
    expect(platformIconSrc("dreamcast", "dc")).toBe("/assets/platforms/dc.svg");
  });

  it("uses the default when nothing shipped", () => {
    expect(platformIconSrc("switch_mods")).toBe(DEFAULT_PLATFORM_ICON);
  });
});

describe("listShippedPlatformIcons", () => {
  it("returns sorted slug and url pairs from the build allowlist", () => {
    const entries = listShippedPlatformIcons();

    expect(entries.length).toBeGreaterThan(10);
    const slugs = entries.map((e) => e.slug);
    expect(slugs).toEqual([...slugs].sort((a, b) => a.localeCompare(b)));
    expect(entries.find((e) => e.slug === "snes")).toEqual({
      slug: "snes",
      url: "/assets/platforms/snes.svg",
    });
  });
});
