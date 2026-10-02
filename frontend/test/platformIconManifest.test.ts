import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { listPlatformIcons } from "../scripts/platformIconManifest";

describe("listPlatformIcons", () => {
  it("maps top-level svg and ico files by lowercase slug, svg first", () => {
    const dir = mkdtempSync(join(tmpdir(), "platform-icons-"));
    try {
      const names = [
        "snes.svg",
        "dc.ico",
        "dc.svg",
        "Saturn.ICO",
        "vsmile.png",
        "ATTRIBUTIONS",
      ];
      for (const name of names) writeFileSync(join(dir, name), "");
      mkdirSync(join(dir, "systematic"));
      writeFileSync(join(dir, "systematic", "nes.svg"), "");

      expect(Object.fromEntries(listPlatformIcons(dir))).toEqual({
        dc: "dc.svg",
        saturn: "Saturn.ICO",
        snes: "snes.svg",
      });
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("the shipped platform icons", () => {
  it("are found in public/, so a plain build copies them into dist", () => {
    const icons = listPlatformIcons(resolve("public/assets/platforms"));

    expect(icons.size).toBeGreaterThan(100);
    expect(icons.has("default")).toBe(true);
    expect(icons.has("snes")).toBe(true);
  });
});
