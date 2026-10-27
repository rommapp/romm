import { describe, expect, it } from "vitest";
import enRom from "@/locales/en_US/rom.json";
import { RELEASE_TYPES, releaseTypeLabelKey } from "./releaseTypes";

describe("releaseTypeLabelKey", () => {
  it("maps a snake_case type onto its kebab-case rom key", () => {
    expect(releaseTypeLabelKey("color_patch")).toBe(
      "rom.release-type-color-patch",
    );
  });

  it("has an English label for every release type", () => {
    for (const type of RELEASE_TYPES) {
      const key = releaseTypeLabelKey(type).replace(/^rom\./, "");
      expect(enRom).toHaveProperty([key]);
    }
  });
});
