import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import pendingAssetStore, {
  hasPendingAssets,
  pendingAssetId,
  pendingAssetKinds,
  syncPendingAssets,
  type PendingAsset,
} from "@/services/pending-asset";

const auth = vi.hoisted(() => ({ userId: 1 as number | null }));
vi.mock("@/stores/auth", () => ({
  default: () => ({ user: auth.userId === null ? null : { id: auth.userId } }),
}));

const romApiMocks = vi.hoisted(() => ({ getRom: vi.fn() }));
const saveApiMocks = vi.hoisted(() => ({ uploadSaves: vi.fn() }));
const stateApiMocks = vi.hoisted(() => ({ uploadStates: vi.fn() }));

vi.mock("@/services/api/rom", () => ({ default: romApiMocks }));
vi.mock("@/services/api/save", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/save")>()),
  default: saveApiMocks,
}));
vi.mock("@/services/api/state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/state")>()),
  default: stateApiMocks,
}));

// happy-dom ships no IndexedDB, which is also what a locked-down origin or a
// private window looks like. Losing the frame must never cost the player a save.
describe("pendingAssetStore without IndexedDB", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists nothing rather than throwing", async () => {
    await expect(pendingAssetStore.list()).resolves.toEqual([]);
  });

  it("swallows a write", async () => {
    await expect(
      pendingAssetStore.write({
        id: "1:a",
        kind: "save",
        romId: 1,
        romName: "Game",
        bytes: new Uint8Array([1, 2, 3]).buffer,
        capturedAt: 0,
      }),
    ).resolves.toBeUndefined();
  });

  it("swallows a clear", async () => {
    await expect(pendingAssetStore.clear("1:a")).resolves.toBeUndefined();
  });

  it("reports nothing as held", async () => {
    await expect(pendingAssetKinds(1)).resolves.toEqual(new Set());
  });

  it("has nothing to hand over", async () => {
    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [],
    });
  });
});

describe("pendingAssetId", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keys a capture to its rom", () => {
    expect(pendingAssetId(7)).toMatch(/^7:.+/);
  });

  // Plain http on a LAN address is not a secure context, and there
  // `crypto.randomUUID` does not exist at all.
  it("still hands out distinct ids without randomUUID", () => {
    vi.stubGlobal("crypto", {});

    const first = pendingAssetId(7);
    const second = pendingAssetId(7);

    expect(first).toMatch(/^7:.+/);
    expect(second).not.toBe(first);
  });
});

// The sliver of IndexedDB the store uses, in memory, so the retry itself can
// be exercised rather than only its unavailable-storage fallback.
function installFakeIndexedDB(rows: Map<string, PendingAsset>) {
  function request(result?: unknown) {
    const req: Record<string, unknown> = { result };
    queueMicrotask(() => (req.onsuccess as (() => void) | undefined)?.());
    return req;
  }
  const objectStore = {
    getAll: () => request([...rows.values()]),
    put: (entry: PendingAsset) => {
      rows.set(entry.id, entry);
      return request();
    },
    delete: (id: string) => {
      rows.delete(id);
      return request();
    },
  };
  const db = {
    objectStoreNames: [] as string[],
    createObjectStore: () => objectStore,
    deleteObjectStore: () => undefined,
    close: () => undefined,
    transaction: () => {
      const transaction: Record<string, unknown> = {
        objectStore: () => objectStore,
        error: null,
      };
      queueMicrotask(() =>
        (transaction.oncomplete as (() => void) | undefined)?.(),
      );
      return transaction;
    },
  };
  vi.stubGlobal("indexedDB", {
    open: () => {
      const req: Record<string, unknown> = { result: db };
      queueMicrotask(() => {
        (req.onupgradeneeded as (() => void) | undefined)?.();
        (req.onsuccess as (() => void) | undefined)?.();
      });
      return req;
    },
  });
}

// What axios hands back: a status only when the server answered at all, and a
// body that is a bare string when the backend refused the CSRF token.
function refusal(status?: number, detail?: string, body?: string) {
  return Object.assign(new Error(`Request failed with status code ${status}`), {
    isAxiosError: true,
    response:
      status === undefined
        ? undefined
        : {
            status,
            statusText: `HTTP ${status}`,
            data: body ?? { detail },
          },
  });
}

describe("syncPendingAssets", () => {
  let rows: Map<string, PendingAsset>;
  const bytes = new Uint8Array([1, 2, 3]).buffer;
  const shot = new Uint8Array([9, 9]).buffer;

  // The ids are unique per test: a row the server has taken is remembered for
  // the lifetime of the module, which is what stops it syncing twice.
  function queue(entry: Partial<PendingAsset> & { id: string }) {
    const row: PendingAsset = {
      kind: "save",
      userId: 1,
      romId: 1,
      romName: "Held Game",
      bytes,
      capturedAt: Date.parse("2024-05-06T07:08:09.010Z"),
      ...entry,
    };
    rows.set(row.id, row);
    return row;
  }

  beforeEach(() => {
    rows = new Map();
    auth.userId = 1;
    installFakeIndexedDB(rows);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    romApiMocks.getRom.mockResolvedValue({
      data: {
        id: 1,
        name: "Game",
        fs_name_no_ext: "game",
        path_cover_small: "cover.png",
      },
    });
    saveApiMocks.uploadSaves.mockResolvedValue([{ status: "fulfilled" }]);
    stateApiMocks.uploadStates.mockResolvedValue([{ status: "fulfilled" }]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    romApiMocks.getRom.mockReset();
    saveApiMocks.uploadSaves.mockReset();
    stateApiMocks.uploadStates.mockReset();
  });

  it("hands a held save to the slot it was written for", async () => {
    queue({ id: "save:taken", slot: "main_quest", screenshotBytes: shot });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [{ kind: "save", romId: 1, name: "Game", cover: "cover.png" }],
      dropped: [],
    });

    const request = saveApiMocks.uploadSaves.mock.calls[0][0];
    expect(request).toMatchObject({
      slot: "main_quest",
      autocleanup: false,
      overwrite: false,
    });
    expect(request.savesToUpload[0].screenshotFile.name).toBe("game.png");
    expect(rows.size).toBe(0);
  });

  it("hands a held state over under the name of its capture", async () => {
    queue({ id: "state:taken", kind: "state", screenshotBytes: shot });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [{ kind: "state", romId: 1, name: "Game", cover: "cover.png" }],
      dropped: [],
    });

    const { statesToUpload } = stateApiMocks.uploadStates.mock.calls[0][0];
    expect(statesToUpload[0].stateFile.name).toBe(
      "game [2024-05-06 07-08-09-010].state",
    );
    expect(statesToUpload[0].screenshotFile.name).toBe(
      "game [2024-05-06 07-08-09-010].png",
    );
    expect(rows.size).toBe(0);
  });

  // A server that is down or failing has not judged the asset, so it keeps it.
  it.each([
    ["no response at all", refusal(undefined)],
    ["a server that is failing", refusal(500)],
    ["a session that has expired", refusal(401)],
  ])("holds on through %s", async (_label, reason) => {
    stateApiMocks.uploadStates.mockResolvedValue([
      { status: "rejected", reason },
    ]);
    queue({ id: `state:kept:${Math.random()}`, kind: "state" });

    await expect(syncPendingAssets()).resolves.toMatchObject({
      synced: [],
      dropped: [],
    });

    expect(rows.size).toBe(1);
    await expect(hasPendingAssets()).resolves.toBe(true);
  });

  // Retrying a refusal for the rest of time would only nag the player about
  // progress that is never going through.
  it("drops what the server refused for good and says why", async () => {
    stateApiMocks.uploadStates.mockResolvedValue([
      { status: "rejected", reason: refusal(409, "Slot has a newer save") },
    ]);
    queue({ id: "state:refused", kind: "state" });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [
        {
          kind: "state",
          romId: 1,
          name: "Game",
          cover: "cover.png",
          reason: "Slot has a newer save",
        },
      ],
    });

    expect(rows.size).toBe(0);
    await expect(hasPendingAssets()).resolves.toBe(false);
  });

  // The rom is gone, so the name stored with the row is all there is to go on.
  it("names a game the server no longer knows from the row itself", async () => {
    romApiMocks.getRom.mockRejectedValue(refusal(404, "Rom not found"));
    queue({ id: "save:orphan" });

    await expect(syncPendingAssets()).resolves.toMatchObject({
      dropped: [{ name: "Held Game", reason: "Rom not found" }],
    });

    expect(rows.size).toBe(0);
  });

  // A browser is shared, and progress captured by one account is not another's
  // to hand over.
  it("leaves another account's rows alone", async () => {
    queue({ id: "save:theirs", userId: 2 });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [],
    });
    await expect(pendingAssetKinds(1)).resolves.toEqual(new Set());
    await expect(hasPendingAssets()).resolves.toBe(false);

    expect(saveApiMocks.uploadSaves).not.toHaveBeenCalled();
    expect(rows.size).toBe(1);
  });

  it("stamps a row with the account that captured it", async () => {
    await pendingAssetStore.write({
      id: "save:mine",
      kind: "save",
      romId: 1,
      romName: "Game",
      bytes,
      capturedAt: 0,
    });

    expect(rows.get("save:mine")?.userId).toBe(1);
  });

  // The interceptor fetches a fresh token for this one, so the next pass works.
  it("keeps a save the server turned down over its CSRF token", async () => {
    saveApiMocks.uploadSaves.mockResolvedValue([
      {
        status: "rejected",
        reason: refusal(403, undefined, "CSRF token missing"),
      },
    ]);
    queue({ id: "save:csrf" });

    await expect(syncPendingAssets()).resolves.toMatchObject({ dropped: [] });

    expect(rows.size).toBe(1);
  });

  it("drops a row that holds no bytes rather than uploading nothing", async () => {
    queue({ id: "save:empty", bytes: new ArrayBuffer(0) });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [],
    });

    expect(saveApiMocks.uploadSaves).not.toHaveBeenCalled();
    expect(rows.size).toBe(0);
  });

  // A running session owns its own save, so the caller can ask for the rest.
  it("hands over only the kinds it was asked for", async () => {
    queue({ id: "save:not-asked" });
    queue({ id: "state:asked", kind: "state" });

    await expect(syncPendingAssets(["state"])).resolves.toMatchObject({
      synced: [{ kind: "state" }],
    });

    expect(saveApiMocks.uploadSaves).not.toHaveBeenCalled();
    expect([...rows.keys()]).toEqual(["save:not-asked"]);
  });

  it("reports both kinds a rom is still owed", async () => {
    queue({ id: "save:held" });
    queue({ id: "state:held", kind: "state" });
    queue({ id: "other-rom:held", romId: 2 });

    await expect(pendingAssetKinds(1)).resolves.toEqual(
      new Set(["save", "state"]),
    );
    await expect(pendingAssetKinds(2)).resolves.toEqual(new Set(["save"]));
    await expect(pendingAssetKinds(3)).resolves.toEqual(new Set());
  });
});
