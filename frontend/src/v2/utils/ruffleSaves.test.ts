import { beforeEach, describe, expect, it } from "vitest";
import {
  readRuffleSaves,
  removeRuffleSaves,
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

    const restored = unzipRuffleSaves(zipRuffleSaves(saves));
    writeRuffleSaves(HOST, restored);

    expect(readRuffleSaves(HOST, SWF_PATH)).toEqual(saves);

    removeRuffleSaves(HOST, Object.keys(saves));
    expect(localStorage.length).toBe(0);
  });
});
