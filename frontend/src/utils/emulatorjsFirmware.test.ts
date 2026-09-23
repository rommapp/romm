import { describe, expect, it } from "vitest";
import { puaeFirmwareFiles } from "./emulatorjsFirmware";

const firmware = [
  { id: 1, file_name: "kick34005.A500", missing_from_fs: false },
  { id: 2, file_name: "kick40068.A1200", missing_from_fs: false },
  { id: 3, file_name: "gone.rom", missing_from_fs: true },
];

describe("puaeFirmwareFiles", () => {
  it("places every available Kickstart at its own name in the system directory", () => {
    expect(puaeFirmwareFiles("puae", firmware)).toEqual({
      "/home/web_user/retroarch/userdata/system/kick34005.A500":
        "/api/firmware/1/content/kick34005.A500",
      "/home/web_user/retroarch/userdata/system/kick40068.A1200":
        "/api/firmware/2/content/kick40068.A1200",
    });
  });

  it("does not change firmware loading for another core", () => {
    expect(puaeFirmwareFiles("pcsx_rearmed", firmware)).toEqual({});
  });

  it("ignores unsafe filenames", () => {
    expect(
      puaeFirmwareFiles("puae", [
        { id: 1, file_name: "../other.rom", missing_from_fs: false },
        { id: 2, file_name: "folder\\file.rom", missing_from_fs: false },
      ]),
    ).toEqual({});
  });
});
