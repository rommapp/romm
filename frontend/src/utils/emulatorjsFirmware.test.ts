import { describe, expect, it } from "vitest";
import { firmwareExternalFiles } from "./emulatorjsFirmware";

const kick13 = { id: 1, file_name: "kick34005.A500", missing_from_fs: false };
const kick31 = { id: 2, file_name: "kick40068.A1200", missing_from_fs: false };
const missing = { id: 3, file_name: "gone.rom", missing_from_fs: true };
const bundle = { id: 4, file_name: "bios.zip", missing_from_fs: false };
const firmware = [kick13, kick31, missing, bundle];

describe("firmwareExternalFiles", () => {
  it("places every available Kickstart in the PUAE system directory", () => {
    expect(firmwareExternalFiles("puae", firmware, null)).toEqual({
      "/home/web_user/retroarch/userdata/system/kick34005.A500":
        "/api/firmware/1/content/kick34005.A500",
      "/home/web_user/retroarch/userdata/system/kick40068.A1200":
        "/api/firmware/2/content/kick40068.A1200",
    });
  });

  it("leaves the selected file to EJS_biosUrl for PUAE", () => {
    expect(firmwareExternalFiles("puae", firmware, kick13)).toEqual({
      "/home/web_user/retroarch/userdata/system/kick40068.A1200":
        "/api/firmware/2/content/kick40068.A1200",
    });
  });

  it("passes every file next to the game for other cores when none is selected", () => {
    expect(firmwareExternalFiles("melonds", firmware, null)).toEqual({
      "/kick34005.A500": "/api/firmware/1/content/kick34005.A500",
      "/kick40068.A1200": "/api/firmware/2/content/kick40068.A1200",
    });
  });

  it("passes nothing extra for other cores once a file is selected", () => {
    expect(firmwareExternalFiles("pcsx_rearmed", firmware, kick13)).toEqual({});
  });

  it("ignores unsafe filenames", () => {
    expect(
      firmwareExternalFiles(
        "puae",
        [
          { id: 1, file_name: "../other.rom", missing_from_fs: false },
          { id: 2, file_name: "folder\\file.rom", missing_from_fs: false },
        ],
        null,
      ),
    ).toEqual({});
  });
});
