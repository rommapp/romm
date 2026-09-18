import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import type {
  PendingAssetKind,
  PendingSyncResult,
} from "@/services/pending-asset";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import { installPendingAssetSync } from "./index";

type Entry = { id: string; romId: number; kind: PendingAssetKind };
const queue = { entries: [] as Entry[] };
// The server takes everything unless a test says otherwise.
async function acceptAll(
  kinds: readonly PendingAssetKind[] = ["save", "state"],
): Promise<PendingSyncResult> {
  const taken = queue.entries.filter((entry) => kinds.includes(entry.kind));
  queue.entries = queue.entries.filter((entry) => !kinds.includes(entry.kind));
  return {
    synced: taken.map((entry) => ({
      kind: entry.kind,
      romId: entry.romId,
      name: "Game",
      cover: null,
    })),
    dropped: [],
  };
}
const syncPendingAssets = vi.fn(acceptAll);

vi.mock("@/services/pending-asset", () => ({
  syncPendingAssets: (kinds?: PendingAssetKind[]) => syncPendingAssets(kinds),
  hasPendingAssets: async (
    kinds: readonly PendingAssetKind[] = ["save", "state"],
  ) => queue.entries.some((entry) => kinds.includes(entry.kind)),
}));

const success = vi.fn();
const error = vi.fn();
const warning = vi.fn();
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success,
    error,
    warning,
    info: vi.fn(),
  }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const refetchRom = vi.fn(async () => null);
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom }),
}));

const isOffline = ref(false);
vi.mock("@/v2/composables/useServerConnection", () => ({
  useServerConnection: () => ({ isOffline, retryNow: vi.fn() }),
}));

// The composable only runs inside a component scope, like AppLayout's. The
// wrapper is kept so each test's watcher dies with it, rather than answering
// the next test's reconnect.
let wrapper: ReturnType<typeof mount> | null = null;
function install() {
  wrapper = mount(
    defineComponent({
      setup() {
        installPendingAssetSync();
        return () => null;
      },
    }),
  );
}

// Lets the watch, the drain and the queue re-read settle.
async function settle() {
  for (let i = 0; i < 6; i++) await nextTick();
}

describe("installPendingAssetSync", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    queue.entries = [];
    isOffline.value = false;
    syncPendingAssets.mockReset();
    syncPendingAssets.mockImplementation(acceptAll);
    refetchRom.mockClear();
    success.mockClear();
    error.mockClear();
    warning.mockClear();
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("hands over what the browser is holding as soon as it installs", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();

    expect(syncPendingAssets).toHaveBeenCalledTimes(1);
  });

  it("stops asking once the queue is empty", async () => {
    install();
    await settle();

    await vi.advanceTimersByTimeAsync(120_000);
    await settle();

    expect(syncPendingAssets).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps retrying while a save is still owed", async () => {
    // Refused by the server, so the entry outlives the attempt.
    syncPendingAssets.mockImplementation(async () => ({
      synced: [],
      dropped: [],
    }));
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();
    expect(syncPendingAssets).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30_000);
    await settle();

    expect(syncPendingAssets).toHaveBeenCalledTimes(2);
  });

  // The running session owns its save; nothing but this hands over a state.
  it("leaves a running game its own save but takes its states", async () => {
    queue.entries = [
      { id: "1:a", romId: 1, kind: "save" as const },
      { id: "1:b", romId: 1, kind: "state" as const },
    ];
    storePlaying().setPlaying(true);

    install();
    await settle();

    expect(syncPendingAssets).toHaveBeenCalledWith(["state"]);
    expect(queue.entries.map((entry) => entry.kind)).toEqual(["save"]);
  });

  it("hands the save over once the game is over", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];
    const playing = storePlaying();
    playing.setPlaying(true);

    install();
    await settle();
    expect(queue.entries).toHaveLength(1);

    playing.setPlaying(false);
    await settle();

    expect(syncPendingAssets).toHaveBeenLastCalledWith(["save", "state"]);
    expect(queue.entries).toHaveLength(0);
  });

  it("says which game just reached the server", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();

    expect(success).toHaveBeenCalledWith(
      "play.last-save-synced",
      expect.objectContaining({ image: null }),
    );
  });

  it("tells a state apart from a save", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "state" as const }];

    install();
    await settle();

    expect(success).toHaveBeenCalledWith(
      "play.last-state-synced",
      expect.anything(),
    );
  });

  // The progress is gone from the browser, so the reason is all the player has.
  it("says why the server refused what it dropped", async () => {
    syncPendingAssets.mockImplementation(async () => {
      queue.entries = [];
      return {
        synced: [],
        dropped: [
          {
            kind: "save" as const,
            romId: 1,
            name: "Game",
            cover: null,
            reason: "Slot has a newer save",
          },
        ],
      };
    });
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();

    expect(error).toHaveBeenCalledWith(
      "play.save-sync-refused",
      expect.anything(),
    );
    expect(success).not.toHaveBeenCalled();
  });

  // Another device's newer progress holds the slot, so the copy went aside.
  it("says a save was kept apart from its slot", async () => {
    syncPendingAssets.mockImplementation(async () => {
      queue.entries = [];
      return {
        synced: [
          {
            kind: "save" as const,
            romId: 1,
            name: "Game",
            cover: null,
            archived: true as const,
          },
        ],
        dropped: [],
      };
    });
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();

    expect(warning).toHaveBeenCalledWith(
      "play.save-kept-apart",
      expect.anything(),
    );
    expect(success).not.toHaveBeenCalled();
  });

  // Two tabs must not upload the same rows; the one without the lock waits.
  it("leaves the pass to the tab holding the lock", async () => {
    vi.stubGlobal("navigator", {
      locks: {
        request: async (
          _name: string,
          _options: object,
          run: (lock: null) => Promise<boolean>,
        ) => run(null),
      },
    });
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];

    install();
    await settle();

    expect(syncPendingAssets).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(1);
  });

  it("owes a game one line however many states it was holding", async () => {
    queue.entries = [
      { id: "1:a", romId: 1, kind: "state" as const },
      { id: "1:b", romId: 1, kind: "state" as const },
      { id: "1:c", romId: 1, kind: "save" as const },
    ];

    install();
    await settle();

    expect(success).toHaveBeenCalledTimes(2);
  });

  it("waits for the server to come back", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];
    isOffline.value = true;

    install();
    await settle();
    expect(syncPendingAssets).not.toHaveBeenCalled();

    isOffline.value = false;
    await settle();

    expect(syncPendingAssets).toHaveBeenCalledTimes(1);
  });

  // Nothing gets through offline, and reconnecting starts a pass of its own.
  it("stops asking while the server is away", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];
    isOffline.value = true;

    install();
    await settle();
    await vi.advanceTimersByTimeAsync(120_000);
    await settle();

    expect(syncPendingAssets).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  // The running session retries its own save, so there is nothing to wait for.
  it("stops asking in game when only the session's save is held", async () => {
    queue.entries = [{ id: "1:a", romId: 1, kind: "save" as const }];
    storePlaying().setPlaying(true);

    install();
    await settle();

    expect(vi.getTimerCount()).toBe(0);
  });

  it("refreshes the details view of a game that just synced", async () => {
    storeRoms().setCurrentRom({ id: 1 } as DetailedRom);
    queue.entries = [{ id: "1:a", romId: 1, kind: "state" as const }];

    install();
    await settle();

    expect(refetchRom).toHaveBeenCalledWith(1);
  });
});
