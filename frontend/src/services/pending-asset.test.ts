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

  // A private window looks the same: the player must hear nothing was kept.
  it("says a write kept nothing rather than throwing", async () => {
    await expect(
      pendingAssetStore.write({
        id: "1:a",
        kind: "save",
        romId: 1,
        romName: "Game",
        bytes: new Uint8Array([1, 2, 3]).buffer,
        capturedAt: 0,
      }),
    ).resolves.toBe(false);
  });

  it("swallows a clear", async () => {
    await expect(pendingAssetStore.clear("1:a")).resolves.toBeUndefined();
  });

  it("reports nothing as held", async () => {
    await expect(pendingAssetKinds(1)).resolves.toEqual(new Set());
    await expect(hasPendingAssets()).resolves.toBe(false);
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
  type Request = { result?: unknown; onsuccess?: () => void };
  type Transaction = { oncomplete?: () => void };

  // A request settles on the next microtask and then commits its transaction.
  function settle(transaction: Transaction, result?: unknown): Request {
    const request: Request = { result };
    queueMicrotask(() => {
      request.onsuccess?.();
      transaction.oncomplete?.();
    });
    return request;
  }

  // The owner index holds a row only when every part of its key is set, and
  // walks them in key order, a game's captures oldest first.
  function keyCursor(transaction: Transaction): Request {
    const key = (row: PendingAsset) =>
      [row.userId, row.kind, row.romId, row.capturedAt] as (number | string)[];
    const indexed = [...rows.values()]
      .filter((row) => row.userId != null)
      .sort((a, b) => {
        const [left, right] = [key(a), key(b)];
        const at = left.findIndex((part, i) => part !== right[i]);
        return at < 0 ? 0 : left[at] < right[at] ? -1 : 1;
      });
    const request: Request = {};
    let next = 0;
    const step = () => {
      const row = indexed[next++];
      request.result = row
        ? {
            key: [row.userId, row.kind, row.romId],
            primaryKey: row.id,
            continue: () => queueMicrotask(step),
          }
        : null;
      request.onsuccess?.();
      if (!row) transaction.oncomplete?.();
    };
    queueMicrotask(step);
    return request;
  }

  function objectStore(transaction: Transaction) {
    return {
      indexNames: Object.assign([] as string[], { contains: () => false }),
      createIndex: () => undefined,
      deleteIndex: () => undefined,
      get: (id: string) => settle(transaction, rows.get(id)),
      put: (entry: PendingAsset) => {
        rows.set(entry.id, entry);
        return settle(transaction, entry.id);
      },
      delete: (id: string) => {
        rows.delete(id);
        return settle(transaction);
      },
      index: () => ({ openKeyCursor: () => keyCursor(transaction) }),
    };
  }

  const db = {
    objectStoreNames: [] as string[],
    createObjectStore: () => objectStore({}),
    deleteObjectStore: () => undefined,
    close: () => undefined,
    transaction: () => {
      const transaction: Transaction & { objectStore?: unknown } = {};
      transaction.objectStore = () => objectStore(transaction);
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
      fsNameNoExt: "game",
      cover: "cover.png",
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
      synced: [
        { kind: "save", romId: 1, name: "Held Game", cover: "cover.png" },
      ],
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
      synced: [
        { kind: "state", romId: 1, name: "Held Game", cover: "cover.png" },
      ],
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
          name: "Held Game",
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
    saveApiMocks.uploadSaves.mockResolvedValue([
      { status: "rejected", reason: refusal(404, "Rom not found") },
    ]);
    queue({ id: "save:orphan" });

    await expect(syncPendingAssets()).resolves.toMatchObject({
      dropped: [{ name: "Held Game", reason: "Rom not found" }],
    });

    expect(romApiMocks.getRom).not.toHaveBeenCalled();
    expect(rows.size).toBe(0);
  });

  // A row from before the stem was stored asks the rom for it instead.
  it("names an older row's files after the rom it belongs to", async () => {
    queue({ id: "save:older", fsNameNoExt: undefined, screenshotBytes: shot });

    await syncPendingAssets();

    expect(romApiMocks.getRom).toHaveBeenCalledWith({ romId: 1 });
    const request = saveApiMocks.uploadSaves.mock.calls[0][0];
    expect(request.savesToUpload[0].screenshotFile.name).toBe("game.png");
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
    await expect(
      pendingAssetStore.write({
        id: "save:mine",
        kind: "save",
        romId: 1,
        romName: "Game",
        bytes,
        capturedAt: 0,
      }),
    ).resolves.toBe(true);

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

  // The newest capture has to land last, or the slot's newest version is stale.
  it("hands a game's captures over oldest first", async () => {
    queue({
      id: "save:captured-last",
      capturedAt: 2_000,
      bytes: new Uint8Array([2]).buffer,
    });
    queue({
      id: "save:captured-first",
      capturedAt: 1_000,
      bytes: new Uint8Array([1]).buffer,
    });

    await syncPendingAssets();

    const uploaded = await Promise.all(
      saveApiMocks.uploadSaves.mock.calls.map(async ([request]) => {
        const file: File = request.savesToUpload[0].saveFile;
        return new Uint8Array(await file.arrayBuffer())[0];
      }),
    );
    expect(uploaded).toEqual([1, 2]);
  });

  // Signing out mid-pass must not hand the rest to whoever signs in next.
  it("stops a pass once the account that started it is gone", async () => {
    queue({ id: "save:first", capturedAt: 1 });
    queue({ id: "save:second", capturedAt: 2 });
    saveApiMocks.uploadSaves.mockImplementation(async () => {
      auth.userId = 2;
      return [{ status: "fulfilled" }];
    });

    await syncPendingAssets();

    expect(saveApiMocks.uploadSaves).toHaveBeenCalledTimes(1);
    expect(rows.has("save:second")).toBe(true);
  });

  // Newer progress from another device holds the slot; neither copy is lost.
  it("keeps a save the slot refuses as a separate save", async () => {
    saveApiMocks.uploadSaves
      .mockResolvedValueOnce([
        { status: "rejected", reason: refusal(409, "Slot has a newer save") },
      ])
      .mockResolvedValueOnce([{ status: "fulfilled" }]);
    queue({ id: "save:conflict", slot: "autosave", screenshotBytes: shot });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [
        {
          kind: "save",
          romId: 1,
          name: "Held Game",
          cover: "cover.png",
          archived: true,
        },
      ],
      dropped: [],
    });

    const archive = saveApiMocks.uploadSaves.mock.calls[1][0];
    expect(archive.slot).toBeUndefined();
    expect(archive.savesToUpload[0].saveFile.name).toBe(
      "game [2024-05-06 07-08-09-010].srm",
    );
    expect(archive.savesToUpload[0].screenshotFile.name).toBe(
      "game [2024-05-06 07-08-09-010].png",
    );
    expect(rows.size).toBe(0);
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
