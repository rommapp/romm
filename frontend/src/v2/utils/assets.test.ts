import { describe, expect, it } from "vitest";
import { saveFixture } from "@/utils/assets.fixtures";
import { isSaveArchive } from "./assets";

describe("isSaveArchive", () => {
  it.each([
    "game [retroarch 2026-10-02 12-00-00].saves.zip",
    "card [2026-10-02 12-00-00].card.zip",
    "PSP-ULUS10041.zip",
    "GAME.ZIP",
  ])("takes %s for an archive", (file_name) => {
    expect(isSaveArchive(saveFixture({ file_name }))).toBe(true);
  });

  it.each(["game.srm", "game.sav", "game.zip.srm"])(
    "takes %s for a raw save",
    (file_name) => {
      expect(isSaveArchive(saveFixture({ file_name }))).toBe(false);
    },
  );
});
