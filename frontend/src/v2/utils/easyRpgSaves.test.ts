import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import { saveFixture } from "@/utils/assets.fixtures";
import {
  clearEasyRpgSaves,
  type EasyRpgSave,
  EasyRpgSaveSync,
  easyRpgServerSaves,
  planEasyRpgLaunch,
  readEasyRpgSaves,
  writeEasyRpgSaves,
} from "./easyRpgSaves";

const saveApiMocks = vi.hoisted(() => ({
  uploadSaves: vi.fn(),
  sendSaveOnUnload: vi.fn(),
}));
vi.mock("@/services/api/save", () => ({ default: saveApiMocks }));

const GAME = "42";
const EARLIER = "2026-01-01T00:00:00.000Z";
const LATER = "2026-02-01T00:00:00.000Z";

function localSave(name: string, modified: string, byte = 1): EasyRpgSave {
  return { name, bytes: new Uint8Array([byte]), modified: new Date(modified) };
}

function serverSave(
  file_name: string,
  updated_at: string,
  overrides: Partial<SaveSchema> = {},
): SaveSchema {
  return saveFixture({
    id: Number(file_name.match(/\d+/)?.[0] ?? 1),
    file_name,
    updated_at,
    emulator: "easyrpg",
    download_path: `/api/saves/1/content/${file_name}`,
    ...overrides,
  });
}

async function playerSaves(game = GAME) {
  return (await readEasyRpgSaves(game)).map(({ name, bytes, modified }) => [
    name,
    Array.from(bytes),
    modified.toISOString(),
  ]);
}

afterEach(async () => {
  await clearEasyRpgSaves(GAME);
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("player save storage", () => {
  it("round-trips saves in the database the player mounts", async () => {
    await writeEasyRpgSaves(GAME, [localSave("Save01.lsd", EARLIER, 7)]);

    expect(await playerSaves()).toEqual([["Save01.lsd", [7], EARLIER]]);
    const names = (await indexedDB.databases()).map((db) => db.name);
    expect(names).toContain("/easyrpg/42/Save");
  });

  it("keeps each game's saves apart", async () => {
    await writeEasyRpgSaves("7", [localSave("Save01.lsd", EARLIER)]);

    expect(await playerSaves()).toEqual([]);
    await clearEasyRpgSaves("7");
  });

  it("ignores files that are not save slots", async () => {
    await writeEasyRpgSaves(GAME, [
      localSave("Save01.lsd", EARLIER),
      localSave("notes.txt", EARLIER),
    ]);

    expect((await playerSaves()).map(([name]) => name)).toEqual(["Save01.lsd"]);
  });
});

describe("easyRpgServerSaves", () => {
  it("keeps the player's own unslotted save files", () => {
    const own = serverSave("Save01.lsd", EARLIER);

    expect(
      easyRpgServerSaves([
        own,
        serverSave("Save02.lsd", EARLIER, { emulator: "snes9x" }),
        serverSave("Save03.lsd", EARLIER, { slot: "autosave" }),
        serverSave("game.srm", EARLIER),
      ]),
    ).toEqual([own]);
  });
});

describe("planEasyRpgLaunch", () => {
  it("takes the newer copy of each file", () => {
    const newerOnServer = serverSave("Save01.lsd", LATER);
    const olderOnServer = serverSave("Save02.lsd", EARLIER);
    const onlyOnServer = serverSave("Save03.lsd", EARLIER);
    const newerHere = localSave("Save02.lsd", LATER);
    const onlyHere = localSave("Save04.lsd", EARLIER);

    const plan = planEasyRpgLaunch(
      [newerOnServer, olderOnServer, onlyOnServer],
      [localSave("Save01.lsd", EARLIER), newerHere, onlyHere],
    );

    expect(plan.download).toEqual([newerOnServer, onlyOnServer]);
    expect(plan.upload).toEqual([newerHere, onlyHere]);
  });

  it("leaves files that match alone", () => {
    const plan = planEasyRpgLaunch(
      [serverSave("Save01.lsd", EARLIER)],
      [localSave("Save01.lsd", EARLIER)],
    );

    expect(plan).toEqual({ download: [], upload: [] });
  });
});

describe("EasyRpgSaveSync", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn(async () => new Response(new Uint8Array([9])));
    vi.stubGlobal("fetch", fetchMock);
    saveApiMocks.uploadSaves.mockImplementation(
      async ({ savesToUpload }: { savesToUpload: { saveFile: File }[] }) => [
        {
          status: "fulfilled",
          value: serverSave(savesToUpload[0]!.saveFile.name, LATER),
        },
      ],
    );
  });

  function sync(saves: SaveSchema[] = []) {
    return new EasyRpgSaveSync({ id: 42, user_saves: saves }, GAME);
  }

  it("loads the server's saves into the player", async () => {
    await sync([serverSave("Save01.lsd", EARLIER)]).prepare(1);

    expect(fetchMock).toHaveBeenCalledWith("/api/saves/1/content/Save01.lsd", {
      credentials: "same-origin",
    });
    expect(await playerSaves()).toEqual([["Save01.lsd", [9], EARLIER]]);
  });

  it("drops the saves another account left in this browser", async () => {
    await sync().prepare(1);
    await writeEasyRpgSaves(GAME, [localSave("Save01.lsd", EARLIER)]);

    await sync().prepare(2);

    expect(await playerSaves()).toEqual([]);
  });

  it("keeps the same account's saves between launches", async () => {
    await sync().prepare(1);
    await writeEasyRpgSaves(GAME, [localSave("Save01.lsd", EARLIER)]);

    const next = sync();
    await next.prepare(1);

    expect(await playerSaves()).toHaveLength(1);
    // Never uploaded, so the next push sends it.
    await next.push();
    expect(saveApiMocks.uploadSaves).toHaveBeenCalledTimes(1);
  });

  it("uploads only the saves the player changed", async () => {
    const session = sync([serverSave("Save01.lsd", EARLIER)]);
    await session.prepare(1);
    await writeEasyRpgSaves(GAME, [localSave("Save02.lsd", LATER, 3)]);

    expect(await session.push()).toBe(true);
    expect(await session.push()).toBe(true);

    expect(saveApiMocks.uploadSaves).toHaveBeenCalledTimes(1);
    const [{ emulator, savesToUpload }] = saveApiMocks.uploadSaves.mock
      .calls[0] as [{ emulator: string; savesToUpload: { saveFile: File }[] }];
    expect(emulator).toBe("easyrpg");
    expect(savesToUpload[0]!.saveFile.name).toBe("Save02.lsd");
  });

  it("retries a save that failed to upload", async () => {
    const session = sync();
    await session.prepare(1);
    await writeEasyRpgSaves(GAME, [localSave("Save01.lsd", LATER)]);
    saveApiMocks.uploadSaves.mockResolvedValueOnce([
      { status: "rejected", reason: new Error("offline") },
    ]);

    expect(await session.push()).toBe(false);
    expect(await session.push()).toBe(true);
    expect(saveApiMocks.uploadSaves).toHaveBeenCalledTimes(2);
  });

  it("sends pending saves as the page unloads, updating known ones", async () => {
    const stored = serverSave("Save01.lsd", EARLIER);
    const session = sync([stored]);
    await session.prepare(1);
    await writeEasyRpgSaves(GAME, [localSave("Save01.lsd", LATER)]);
    saveApiMocks.uploadSaves.mockResolvedValueOnce([
      { status: "rejected", reason: new Error("offline") },
    ]);
    await session.push();

    session.pushOnUnload();

    expect(saveApiMocks.sendSaveOnUnload).toHaveBeenCalledWith(
      expect.objectContaining({ emulator: "easyrpg", save: stored }),
    );
  });
});
