import { AxiosError, AxiosHeaders } from "axios";
import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SyncOperationSchema } from "@/__generated__";
import { saveContentHash } from "./hash";
import { DeviceSaveSync, type PlayerSaveFile } from "./index";
import { listLocalSaves } from "./localSaves";

const mocks = vi.hoisted(() => ({
  browserDeviceId: vi.fn(),
  negotiate: vi.fn(),
  completeSession: vi.fn(),
  downloadSave: vi.fn(),
  confirmDownloaded: vi.fn(),
  uploadSaves: vi.fn(),
  sendSaveOnUnload: vi.fn(),
}));

vi.mock("./browserDevice", () => ({ browserDeviceId: mocks.browserDeviceId }));

vi.mock("@/services/api/sync", () => ({
  default: {
    negotiate: mocks.negotiate,
    completeSession: mocks.completeSession,
    downloadSave: mocks.downloadSave,
    confirmDownloaded: mocks.confirmDownloaded,
  },
}));

vi.mock("@/services/api/save", () => ({
  default: {
    uploadSaves: mocks.uploadSaves,
    sendSaveOnUnload: mocks.sendSaveOnUnload,
  },
}));

const ROM = { id: 5, fs_name_no_ext: "Yume Nikki" };
let userId = 0;

function httpError(status: number): AxiosError {
  return new AxiosError("failed", "ERR", undefined, undefined, {
    status,
    statusText: "",
    data: null,
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

function playerSave(
  slot: string,
  content: number,
  updatedAt = 1000,
): PlayerSaveFile {
  return {
    slot,
    fileName: `${slot}.lsd`,
    bytes: new Uint8Array([content]),
    updatedAt,
  };
}

function operation(
  action: SyncOperationSchema["action"],
  overrides: Partial<SyncOperationSchema> = {},
): SyncOperationSchema {
  return {
    action,
    rom_id: ROM.id,
    slot: "Save01",
    file_name: "Save01 [2026-01-01_00-00-00].lsd",
    reason: "",
    ...overrides,
  };
}

function negotiated(operations: SyncOperationSchema[]) {
  mocks.negotiate.mockResolvedValueOnce({
    data: { session_id: 9, operations },
  });
}

function sync(): DeviceSaveSync {
  return new DeviceSaveSync(ROM, userId, "easyrpg");
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  // A fresh account per test keeps the shared fake database apart.
  userId += 1;
  mocks.browserDeviceId.mockResolvedValue("device-1");
  mocks.completeSession.mockResolvedValue({});
  mocks.confirmDownloaded.mockResolvedValue({});
  mocks.uploadSaves.mockResolvedValue([{ status: "fulfilled", value: {} }]);
});

describe("DeviceSaveSync.prepare", () => {
  it("downloads what the server holds and confirms it", async () => {
    negotiated([
      operation("download", {
        save_id: 3,
        server_updated_at: "2026-01-01T00:00:00Z",
      }),
    ]);
    mocks.downloadSave.mockResolvedValue({ data: new Uint8Array([7]).buffer });

    const saves = await sync().prepare();

    expect(mocks.negotiate).toHaveBeenCalledWith({
      deviceId: "device-1",
      romIds: [ROM.id],
      saves: [],
    });
    expect(saves.map((save) => [save.slot, [...save.bytes]])).toEqual([
      ["Save01", [7]],
    ]);
    const hash = saveContentHash(new Uint8Array([7]));
    expect(mocks.confirmDownloaded).toHaveBeenCalledWith({
      saveId: 3,
      deviceId: "device-1",
      contentHash: hash,
    });
    expect(mocks.completeSession).toHaveBeenCalledWith(9, {
      operations_completed: 1,
      operations_failed: 0,
    });
  });

  it("uploads a save the player holds that the server lacks", async () => {
    negotiated([operation("upload")]);

    await sync().prepare([playerSave("Save01", 1)]);

    expect(mocks.negotiate.mock.calls[0]![0].saves).toEqual([
      expect.objectContaining({
        slot: "Save01",
        file_name: "Save01.lsd",
        content_hash: saveContentHash(new Uint8Array([1])),
        file_size_bytes: 1,
      }),
    ]);
    expect(mocks.uploadSaves).toHaveBeenCalledWith(
      expect.objectContaining({
        deviceId: "device-1",
        slot: "Save01",
        sessionId: 9,
        overwrite: true,
        autocleanup: true,
      }),
    );
    const [held] = await listLocalSaves(userId, ROM.id);
    expect(held!.syncedHash).toBe(held!.hash);
  });

  it("archives this copy and plays the server's on a conflict", async () => {
    negotiated([operation("conflict", { save_id: 3 })]);
    mocks.downloadSave.mockResolvedValue({ data: new Uint8Array([9]).buffer });

    const saves = await sync().prepare([playerSave("Save01", 1)]);

    const archived = mocks.uploadSaves.mock.calls[0]![0];
    expect(archived.slot).toBeUndefined();
    expect(archived.savesToUpload[0].saveFile.name).toMatch(
      /^Yume Nikki \[.+\]\.lsd$/,
    );
    expect([...saves[0]!.bytes]).toEqual([9]);
  });

  it("drops a slot the server emptied", async () => {
    negotiated([operation("delete")]);

    const saves = await sync().prepare([playerSave("Save01", 1)]);

    expect(saves).toEqual([]);
    expect(await listLocalSaves(userId, ROM.id)).toEqual([]);
  });

  it("plays what this browser holds when the server is unreachable", async () => {
    mocks.negotiate.mockRejectedValueOnce(new Error("offline"));

    const saves = await sync().prepare([playerSave("Save01", 1)]);

    expect(saves.map((save) => save.slot)).toEqual(["Save01"]);
  });

  it("registers again when the device was removed", async () => {
    mocks.negotiate.mockRejectedValueOnce(httpError(404));
    mocks.browserDeviceId.mockResolvedValueOnce("gone");
    mocks.browserDeviceId.mockResolvedValueOnce("device-2");
    negotiated([]);

    await sync().prepare();

    expect(mocks.browserDeviceId).toHaveBeenLastCalledWith(userId, {
      refresh: true,
    });
    expect(mocks.negotiate.mock.calls[1]![0].deviceId).toBe("device-2");
  });
});

describe("DeviceSaveSync.push", () => {
  it("uploads only what changed, guarded against other devices", async () => {
    negotiated([]);
    const saveSync = sync();
    await saveSync.prepare();

    await saveSync.capture([playerSave("Save01", 1), playerSave("Save02", 2)]);
    expect(await saveSync.push()).toBe(true);
    expect(await saveSync.push()).toBe(true);

    expect(mocks.uploadSaves).toHaveBeenCalledTimes(2);
    expect(mocks.uploadSaves.mock.calls[0]![0]).toMatchObject({
      overwrite: false,
      deviceId: "device-1",
    });
  });

  it("archives a save another device wrote over meanwhile", async () => {
    negotiated([]);
    const saveSync = sync();
    await saveSync.prepare();
    mocks.uploadSaves.mockResolvedValueOnce([
      { status: "rejected", reason: httpError(409) },
    ]);

    await saveSync.capture([playerSave("Save01", 1)]);

    expect(await saveSync.push()).toBe(true);
    expect(mocks.uploadSaves).toHaveBeenCalledTimes(2);
    expect(mocks.uploadSaves.mock.calls[1]![0].slot).toBeUndefined();
  });

  it("keeps a save captured while the previous one uploaded", async () => {
    negotiated([]);
    const saveSync = sync();
    await saveSync.prepare();
    let finishUpload: () => void = () => undefined;
    mocks.uploadSaves.mockReturnValueOnce(
      new Promise((resolve) => {
        finishUpload = () => resolve([{ status: "fulfilled", value: {} }]);
      }),
    );

    await saveSync.capture([playerSave("Save01", 1)]);
    const pushing = saveSync.push();
    await vi.waitFor(() => expect(mocks.uploadSaves).toHaveBeenCalled());
    await saveSync.capture([playerSave("Save01", 2, 2000)]);
    finishUpload();
    await pushing;

    const [held] = await listLocalSaves(userId, ROM.id);
    expect([...held!.bytes]).toEqual([2]);
    expect(held!.syncedHash).toBe(saveContentHash(new Uint8Array([1])));
  });

  it("sends what the player wrote as the page goes away", async () => {
    negotiated([]);
    const saveSync = sync();
    await saveSync.prepare();

    saveSync.captureOnUnload([playerSave("Save01", 1)]);

    expect(mocks.sendSaveOnUnload).toHaveBeenCalledWith(
      expect.objectContaining({
        deviceId: "device-1",
        slot: "Save01",
        contentHash: saveContentHash(new Uint8Array([1])),
        overwrite: false,
      }),
    );
    await vi.waitFor(async () =>
      expect(await listLocalSaves(userId, ROM.id)).toHaveLength(1),
    );
  });

  it("keeps saves in the browser when the account cannot sync", async () => {
    mocks.browserDeviceId.mockResolvedValue(null);
    const saveSync = sync();
    await saveSync.prepare();

    await saveSync.capture([playerSave("Save01", 1)]);

    expect(await saveSync.push()).toBe(true);
    expect(mocks.negotiate).not.toHaveBeenCalled();
    expect(mocks.uploadSaves).not.toHaveBeenCalled();
  });
});
