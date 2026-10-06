import { describe, expect, it } from "vitest";
import { saveFixture } from "@/utils/assets.fixtures";
import { browserSaves } from "./assets";

describe("browserSaves", () => {
  it("drops the saves the server flags as zipped", () => {
    const raw = saveFixture({ id: 1, file_name: "game.srm" });
    const zipped = saveFixture({
      id: 2,
      file_name: "game.bin",
      is_zipped: true,
    });

    expect(browserSaves([raw, zipped])).toEqual([raw]);
  });

  it("goes by the flag, not the file name", () => {
    const save = saveFixture({ file_name: "game.zip", is_zipped: false });

    expect(browserSaves([save])).toEqual([save]);
  });
});

describe("saveFixture", () => {
  it.each([
    ["game [retroarch 2026-10-02 12-00-00].saves.zip", true],
    ["GAME.ZIP", true],
    ["game.srm", false],
  ])("flags %s as the server would", (file_name, zipped) => {
    expect(saveFixture({ file_name }).is_zipped).toBe(zipped);
  });
});
