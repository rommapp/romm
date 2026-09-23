import { describe, expect, it } from "vitest";
import {
  indexShippedPlatformIcons,
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
