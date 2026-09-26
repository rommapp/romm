import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { listPlatformIconFiles } from "../scripts/platformIconManifest";

describe("listPlatformIconFiles", () => {
  it("lists top-level svg and ico files only, sorted", () => {
    const dir = mkdtempSync(join(tmpdir(), "platform-icons-"));
    for (const name of ["snes.svg", "dc.ico", "vsmile.png", "ATTRIBUTIONS"]) {
      writeFileSync(join(dir, name), "");
    }
    mkdirSync(join(dir, "systematic"));
    writeFileSync(join(dir, "systematic", "nes.svg"), "");

    expect(listPlatformIconFiles(dir)).toEqual(["dc.ico", "snes.svg"]);
  });
});
