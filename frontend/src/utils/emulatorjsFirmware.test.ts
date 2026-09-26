import { describe, expect, it } from "vitest";
import { firmwareExternalFiles } from "./emulatorjsFirmware";

const firmware = [
  { id: 1, file_name: "kick34005.A500", missing_from_fs: false },
  { id: 2, file_name: "kick40068.A1200", missing_from_fs: false },
  { id: 3, file_name: "gone.rom", missing_from_fs: true },
  { id: 4, file_name: "bios.zip", missing_from_fs: false },
];

describe("firmwareExternalFiles", () => {
  it("places every available Kickstart in the PUAE system directory", () => {
    expect(firmwareExternalFiles("puae", firmware)).toEqual({
      "/home/web_user/retroarch/userdata/system/kick34005.A500":
        "/api/firmware/1/content/kick34005.A500",
      "/home/web_user/retroarch/userdata/system/kick40068.A1200":
        "/api/firmware/2/content/kick40068.A1200",
    });
  });

  it("does not change firmware loading for another core", () => {
    expect(firmwareExternalFiles("pcsx_rearmed", firmware)).toEqual({});
  });

  it("ignores unsafe filenames", () => {
    expect(
      firmwareExternalFiles("puae", [
        { id: 1, file_name: "../other.rom", missing_from_fs: false },
        { id: 2, file_name: "folder\\file.rom", missing_from_fs: false },
        { id: 3, file_name: "..", missing_from_fs: false },
        { id: 4, file_name: ".", missing_from_fs: false },
      ]),
    ).toEqual({});
  });

  it("encodes the name in the URL but keeps it verbatim in the path", () => {
    expect(
      firmwareExternalFiles("puae", [
        { id: 5, file_name: "kick #1?.rom", missing_from_fs: false },
      ]),
    ).toEqual({
      "/home/web_user/retroarch/userdata/system/kick #1?.rom":
        "/api/firmware/5/content/kick%20%231%3F.rom",
    });
  });
});
