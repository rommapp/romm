import { beforeEach, describe, expect, it } from "vitest";
import {
  readRuffleSaves,
  removeRuffleSaves,
  sameRuffleSaves,
  swfStoragePath,
  unzipRuffleSaves,
  writeRuffleSaves,
  zipRuffleSaves,
} from "./ruffleSaves";

const HOST = "romm.local";
const SWF_PATH = "api/roms/1/content/game.swf";

function sol(marker: number): Uint8Array {
  return new Uint8Array([
    0x00,
    0xbf,
    0,
    0,
    0,
    9,
    0x54,
    0x43,
    0x53,
    0x4f,
    marker,
  ]);
}

function stored(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

beforeEach(() => localStorage.clear());

describe("ruffle saves", () => {
  it("compares two reads byte for byte", () => {
    const saves = { a: sol(1), b: sol(2) };

    expect(sameRuffleSaves(saves, { b: sol(2), a: sol(1) })).toBe(true);
    expect(sameRuffleSaves(saves, { a: sol(1), b: sol(3) })).toBe(false);
    expect(sameRuffleSaves(saves, { a: sol(1) })).toBe(false);
    expect(sameRuffleSaves({ a: sol(1) }, { b: sol(1) })).toBe(false);
  });

  it("derives the storage path from the SWF URL, without its query", () => {
    expect(swfStoragePath("/api/roms/1/content/game.swf?purpose=play")).toBe(
      SWF_PATH,
    );
  });

  it("reads the SharedObjects the SWF can reach, and nothing else", () => {
    localStorage.setItem(`${HOST}/${SWF_PATH}/progress`, stored(sol(1)));
    localStorage.setItem(`${HOST}/api/roms/shared`, stored(sol(2)));
    localStorage.setItem(`${HOST}//root`, stored(sol(3)));
    localStorage.setItem(`${HOST}/${SWF_PATH}/#a/b`, stored(sol(4)));
    localStorage.setItem(
      `${HOST}/api/roms/2/content/other.swf/x`,
      stored(sol(5)),
    );
    localStorage.setItem(`other.host/${SWF_PATH}/progress`, stored(sol(6)));
    localStorage.setItem(`${HOST}/${SWF_PATH}/broken`, "not base64!");
    localStorage.setItem("player:ruffle:1:backgroundColor", "#000000");

    const saves = readRuffleSaves(HOST, SWF_PATH);

    expect(Object.keys(saves).sort()).toEqual(
      [
        `${SWF_PATH}/progress`,
        "api/roms/shared",
        "/root",
        `${SWF_PATH}/#a/b`,
      ].sort(),
    );
    expect(saves[`${SWF_PATH}/progress`]).toEqual(sol(1));
  });

  it("round-trips through a zip and back into storage", () => {
    const saves = { [`${SWF_PATH}/progress`]: sol(1), "/root": sol(3) };

    const restored = unzipRuffleSaves(zipRuffleSaves(saves), SWF_PATH);
    writeRuffleSaves(HOST, restored);

    expect(readRuffleSaves(HOST, SWF_PATH)).toEqual(saves);

    removeRuffleSaves(HOST, Object.keys(saves));
    expect(localStorage.length).toBe(0);
  });

  it("restores only the entries the SWF can reach", () => {
    const archive = zipRuffleSaves({
      [`${SWF_PATH}/progress`]: sol(1),
      "api/roms/2/content/other.swf/progress": sol(2),
    });

    expect(Object.keys(unzipRuffleSaves(archive, SWF_PATH))).toEqual([
      `${SWF_PATH}/progress`,
    ]);
  });
});
