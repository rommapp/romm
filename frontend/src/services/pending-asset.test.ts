import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import pendingAssetStore, {
  hasPendingAssets,
  pendingAssetId,
  pendingAssetKinds,
  syncPendingAssets,
  type PendingAsset,
} from "@/services/pending-asset";
import type {
  HeldPush,
  SnapshotTarget,
} from "@/utils/saveSync/snapshotSession";
import { bankStateFixture, snapshotFixture } from "@/utils/snapshots.fixtures";

const auth = vi.hoisted(() => ({ userId: 1 as number | null }));
vi.mock("@/stores/auth", () => ({
  default: () => ({ user: auth.userId === null ? null : { id: auth.userId } }),
}));

const snapshotApiMocks = vi.hoisted(() => ({ pushSnapshot: vi.fn() }));
vi.mock("@/services/api/snapshot", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/snapshot")>()),
  default: snapshotApiMocks,
}));

const target: SnapshotTarget = {
  romFileId: 7,
  channelId: "chan",
  label: "default",
  expectedCurrentId: 42,
  parentSnapshotId: null,
  bank: { mgba: { auto: "a1" } },
  saveHash: null,
  core: "mgba",
  emulatorVersion: null,
};

/** A row as stored, which one held before channels has no push on. */
type StoredRow = Omit<PendingAsset, "held"> & { held?: HeldPush };

// happy-dom ships no IndexedDB, which is also what a locked-down origin or a
// private window looks like. Losing the frame must never cost the player a save.
describe("pendingAssetStore without IndexedDB", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  // A private window looks the same: the player must hear nothing was kept.
  it("says a write kept nothing rather than throwing", async () => {
    await expect(
      pendingAssetStore.write({
        id: "1:a",
        kind: "save",
        romId: 1,
        romName: "Game",
        held: {
          target,
          content: {
            kind: "save",
            save: { bytes: new ArrayBuffer(3), fileName: "game.srm" },
          },
        },
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
  it("keys a capture to its rom", () => {
    expect(pendingAssetId(7)).toMatch(/^7:.+/);
  });

  // Plain http on a LAN address is not a secure context, and there
  // `crypto.randomUUID` does not exist at all.
  it("still hands out distinct ids without randomUUID", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: crypto.getRandomValues.bind(crypto),
    });

    const first = pendingAssetId(7);
    const second = pendingAssetId(7);

    expect(first).toMatch(/^7:.+/);
    expect(second).not.toBe(first);
  });
});

// The sliver of IndexedDB the store uses, in memory, so the retry itself can
// be exercised rather than only its unavailable-storage fallback.
function installFakeIndexedDB(rows: Map<string, StoredRow>) {
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
    const key = (row: StoredRow) =>
      [row.userId, row.kind, row.romId, row.capturedAt] as (number | string)[];
    const indexed = [...rows.values()]
      .filter((row) => row.userId != null)
      .sort((a, b) => {
        const [left, right] = [key(a), key(b)];
        const at = left.findIndex((part, i) => part !== right[i]);
        return at < 0 ? 0 : left[at]! < right[at]! ? -1 : 1;
      });
    const request: Request = {};
    let next = 0;
    const step = () => {
      const row = indexed[next++];
      request.result = row
        ? {
            key: [row.userId, row.kind, row.romId, row.capturedAt],
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
      put: (entry: StoredRow) => {
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
  let rows: Map<string, StoredRow>;

  function heldSave(byte = 1, base: Partial<SnapshotTarget> = {}): HeldPush {
    return {
      target: { ...target, ...base },
      content: {
        kind: "save",
        save: { bytes: new Uint8Array([byte]).buffer, fileName: "game.srm" },
      },
      deviceId: "device-1",
    };
  }

  function heldState(slot: string): HeldPush {
    return {
      target,
      content: {
        kind: "state",
        slot,
        state: {
          bytes: new Uint8Array([7, slot.length]).buffer,
          fileName: "game.state",
        },
        save: null,
      },
    };
  }

  // The ids are unique per test: a row the server has taken is remembered for
  // the lifetime of the module, which is what stops it syncing twice.
  function queue(entry: Partial<StoredRow> & { id: string }) {
    const row: StoredRow = {
      kind: "save",
      userId: 1,
      romId: 1,
      romName: "Held Game",
      cover: "cover.png",
      held: heldSave(),
      capturedAt: Date.parse("2024-05-06T07:08:09.010Z"),
      ...entry,
    };
    rows.set(row.id, row);
    return row;
  }

  const sentManifests = () =>
    snapshotApiMocks.pushSnapshot.mock.calls.map(
      ([request]) => request.manifest,
    );

  beforeEach(() => {
    rows = new Map();
    auth.userId = 1;
    installFakeIndexedDB(rows);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    snapshotApiMocks.pushSnapshot.mockResolvedValue({
      data: snapshotFixture({ id: 43 }),
    });
  });

  afterEach(() => {
    snapshotApiMocks.pushSnapshot.mockReset();
  });

  it("pushes a held save onto the base it was held on", async () => {
    queue({ id: "save:taken" });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [
        { kind: "save", romId: 1, name: "Held Game", cover: "cover.png" },
      ],
      dropped: [],
    });

    const request = snapshotApiMocks.pushSnapshot.mock.calls[0]![0];
    expect(request.manifest).toMatchObject({
      rom_file_id: 7,
      channel_id: "chan",
      expected_current_id: 42,
      save: { shape: "SINGLE", format: "native" },
    });
    expect(request.deviceId).toBe("device-1");
    expect(request.parts[0].file.name).toBe("game.srm");
    expect(rows.size).toBe(0);
  });

  it("chains pushes held on one base onto what the last one made", async () => {
    const states = {
      mgba: { auto: bankStateFixture("a1"), "1": bankStateFixture("h1") },
    };
    snapshotApiMocks.pushSnapshot
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 50, states }) })
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 51, states }) })
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 52 }) });
    queue({
      id: "chain:first",
      kind: "state",
      capturedAt: 1_000,
      held: heldState("1"),
    });
    queue({ id: "chain:save", capturedAt: 2_000 });
    queue({
      id: "chain:last",
      kind: "state",
      capturedAt: 3_000,
      held: heldState("2"),
    });

    await syncPendingAssets();

    const manifests = sentManifests();
    expect(manifests[0]).toMatchObject({
      expected_current_id: 42,
      states: { mgba: { auto: "a1", "1": expect.any(String) } },
    });
    expect(manifests[1]).toMatchObject({ expected_current_id: 50 });
    expect(manifests[1]).not.toHaveProperty("states");
    expect(manifests[2]).toMatchObject({
      expected_current_id: 51,
      states: { mgba: { auto: "a1", "1": "h1", "2": expect.any(String) } },
    });
  });

  it("sends a push held on another base as it was held", async () => {
    queue({ id: "base:first", capturedAt: 1_000 });
    queue({
      id: "base:other",
      capturedAt: 2_000,
      held: heldSave(2, { expectedCurrentId: 60 }),
    });

    await syncPendingAssets();

    expect(sentManifests().map((m) => m.expected_current_id)).toEqual([42, 60]);
  });

  // A server that is down or failing has not judged the asset, so it keeps it.
  it.each([
    ["no response at all", refusal(undefined)],
    ["a server that is failing", refusal(500)],
    ["a session that has expired", refusal(401)],
  ])("holds on through %s", async (_label, reason) => {
    snapshotApiMocks.pushSnapshot.mockRejectedValue(reason);
    queue({ id: `state:kept:${Math.random()}`, kind: "state" });

    await expect(syncPendingAssets()).resolves.toMatchObject({
      synced: [],
      dropped: [],
    });

    expect(rows.size).toBe(1);
    await expect(hasPendingAssets()).resolves.toBe(true);
  });

  // Retrying a refusal for the rest of time would only nag the player about
  // progress that is never going through. The rom may be gone by then, so the
  // name stored with the row is all there is to go on.
  it("drops what the server refused for good and says why", async () => {
    snapshotApiMocks.pushSnapshot.mockRejectedValue(
      refusal(404, "Rom file not found"),
    );
    queue({ id: "state:refused", kind: "state" });

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [
        {
          kind: "state",
          romId: 1,
          name: "Held Game",
          cover: "cover.png",
          reason: "Rom file not found",
        },
      ],
    });

    expect(rows.size).toBe(0);
    await expect(hasPendingAssets()).resolves.toBe(false);
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

    expect(snapshotApiMocks.pushSnapshot).not.toHaveBeenCalled();
    expect(rows.size).toBe(1);
  });

  it("stamps a row with the account that captured it", async () => {
    await expect(
      pendingAssetStore.write({
        id: "save:mine",
        kind: "save",
        romId: 1,
        romName: "Game",
        held: heldSave(),
        capturedAt: 0,
      }),
    ).resolves.toBe(true);

    expect(rows.get("save:mine")?.userId).toBe(1);
  });

  // The interceptor fetches a fresh token for this one, so the next pass works.
  it("keeps a save the server turned down over its CSRF token", async () => {
    snapshotApiMocks.pushSnapshot.mockRejectedValue(
      refusal(403, undefined, "CSRF token missing"),
    );
    queue({ id: "save:csrf" });

    await expect(syncPendingAssets()).resolves.toMatchObject({ dropped: [] });

    expect(rows.size).toBe(1);
  });

  it("drops a row held before channels, which names no base to push onto", async () => {
    delete queue({ id: "save:legacy" }).held;

    await expect(syncPendingAssets()).resolves.toEqual({
      synced: [],
      dropped: [],
    });

    expect(snapshotApiMocks.pushSnapshot).not.toHaveBeenCalled();
    expect(rows.size).toBe(0);
  });

  // A running session owns its own save, so the caller can ask for the rest.
  it("hands over only the kinds it was asked for", async () => {
    queue({ id: "save:not-asked" });
    queue({ id: "state:asked", kind: "state", held: heldState("1") });

    await expect(syncPendingAssets(["state"])).resolves.toMatchObject({
      synced: [{ kind: "state" }],
    });

    expect(snapshotApiMocks.pushSnapshot).toHaveBeenCalledTimes(1);
    expect([...rows.keys()]).toEqual(["save:not-asked"]);
  });

  // The newest capture has to land last, or the channel's current is stale.
  it("hands a game's captures over oldest first", async () => {
    queue({ id: "save:captured-last", capturedAt: 2_000, held: heldSave(2) });
    queue({ id: "save:captured-first", capturedAt: 1_000, held: heldSave(1) });

    await syncPendingAssets();

    const uploaded = await Promise.all(
      snapshotApiMocks.pushSnapshot.mock.calls.map(async ([request]) => {
        const file: File = request.parts[0].file;
        return new Uint8Array(await file.arrayBuffer())[0];
      }),
    );
    expect(uploaded).toEqual([1, 2]);
  });

  // Signing out mid-pass must not hand the rest to whoever signs in next.
  it("stops a pass once the account that started it is gone", async () => {
    queue({ id: "save:first", capturedAt: 1 });
    queue({ id: "save:second", capturedAt: 2 });
    snapshotApiMocks.pushSnapshot.mockImplementation(() => {
      auth.userId = 2;
      return Promise.resolve({ data: snapshotFixture({ id: 43 }) });
    });

    await syncPendingAssets();

    expect(snapshotApiMocks.pushSnapshot).toHaveBeenCalledTimes(1);
    expect(rows.has("save:second")).toBe(true);
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
