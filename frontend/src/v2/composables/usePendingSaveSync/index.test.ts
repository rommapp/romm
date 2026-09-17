import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import storePlaying from "@/stores/playing";
import { installPendingSaveSync } from "./index";

const queue = { entries: [] as { id: string; romId: number }[] };
// The server takes everything unless a test says otherwise.
async function acceptAll() {
  const taken = queue.entries.map((entry) => ({
    romId: entry.romId,
    name: "Game",
    cover: null,
  }));
  queue.entries = [];
  return taken;
}
const syncPendingSaves = vi.fn(acceptAll);

vi.mock("@/services/pending-save", () => ({
  default: { list: async () => queue.entries },
  syncPendingSaves: () => syncPendingSaves(),
  hasPendingSaves: async () => queue.entries.length > 0,
}));

const success = vi.fn();
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success,
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: vi.fn(async () => ({ data: { id: 1 } })) },
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
        installPendingSaveSync();
        return () => null;
      },
    }),
  );
}

// Lets the watch, the drain and the queue re-read settle.
async function settle() {
  for (let i = 0; i < 6; i++) await nextTick();
}

describe("installPendingSaveSync", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    queue.entries = [];
    isOffline.value = false;
    syncPendingSaves.mockReset();
    syncPendingSaves.mockImplementation(acceptAll);
    success.mockClear();
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.useRealTimers();
  });

  it("hands over what the browser is holding as soon as it installs", async () => {
    queue.entries = [{ id: "1:a", romId: 1 }];

    install();
    await settle();

    expect(syncPendingSaves).toHaveBeenCalledTimes(1);
  });

  it("stops asking once the queue is empty", async () => {
    install();
    await settle();

    await vi.advanceTimersByTimeAsync(120_000);
    await settle();

    expect(syncPendingSaves).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps retrying while a save is still owed", async () => {
    // Refused by the server, so the entry outlives the attempt.
    syncPendingSaves.mockImplementation(async () => []);
    queue.entries = [{ id: "1:a", romId: 1 }];

    install();
    await settle();
    expect(syncPendingSaves).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30_000);
    await settle();

    expect(syncPendingSaves).toHaveBeenCalledTimes(2);
  });

  it("leaves a running game to sync its own session", async () => {
    queue.entries = [{ id: "1:a", romId: 1 }];
    storePlaying().setPlaying(true);

    install();
    await settle();

    expect(syncPendingSaves).not.toHaveBeenCalled();
  });

  it("tries again once the game is over", async () => {
    queue.entries = [{ id: "1:a", romId: 1 }];
    const playing = storePlaying();
    playing.setPlaying(true);

    install();
    await settle();

    playing.setPlaying(false);
    await settle();

    expect(syncPendingSaves).toHaveBeenCalledTimes(1);
  });

  it("says which game just reached the server", async () => {
    queue.entries = [{ id: "1:a", romId: 1 }];

    install();
    await settle();

    expect(success).toHaveBeenCalledWith(
      "play.last-save-synced",
      expect.objectContaining({ image: null }),
    );
  });

  it("waits for the server to come back", async () => {
    queue.entries = [{ id: "1:a", romId: 1 }];
    isOffline.value = true;

    install();
    await settle();
    expect(syncPendingSaves).not.toHaveBeenCalled();

    isOffline.value = false;
    await settle();

    expect(syncPendingSaves).toHaveBeenCalledTimes(1);
  });
});
