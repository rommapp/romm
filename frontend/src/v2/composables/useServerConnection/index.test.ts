import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { nextTick, reactive } from "vue";
import { shouldRefreshOnReconnect } from "./index";

// Each install() leaves an app-lifetime watcher behind, so every test gets
// fresh store objects rather than sharing one the old watchers still see.
function makeHeartbeatStore() {
  return reactive({
    connected: true,
    setConnected(value: boolean) {
      this.connected = value;
    },
    fetchHeartbeat: vi.fn().mockResolvedValue({}),
  });
}

let heartbeatStore = makeHeartbeatStore();
let playingStore = reactive({ playing: false });

vi.mock("@/stores/heartbeat", () => ({ default: () => heartbeatStore }));
vi.mock("@/stores/playing", () => ({ default: () => playingStore }));

const reload = vi.fn();
let originalLocation: Location;

// `installed` is module state, so each test needs a fresh module to install
// its own watchers.
async function install() {
  vi.resetModules();
  const { useServerConnection } = await import("./index");
  return useServerConnection();
}

/** Drive a full offline → online round trip through the store. */
async function goOfflineThenOnline() {
  heartbeatStore.connected = false;
  await nextTick();
  heartbeatStore.connected = true;
  await nextTick();
}

/** A blip survived mid-game, leaving a refresh held back. */
async function playThroughABlip() {
  playingStore.playing = true;
  await nextTick();
  await goOfflineThenOnline();
  expect(reload).not.toHaveBeenCalled();
}

/** The api layer's "no requests left in flight" announcement. */
function quiesce() {
  document.dispatchEvent(new CustomEvent("network-quiesced"));
}

beforeAll(() => {
  originalLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, reload },
  });
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

beforeEach(() => {
  vi.useFakeTimers();
  reload.mockClear();
  heartbeatStore = makeHeartbeatStore();
  playingStore = reactive({ playing: false });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("shouldRefreshOnReconnect", () => {
  it("refreshes only on a real reconnect (offline → online)", () => {
    expect(shouldRefreshOnReconnect(true, false)).toBe(true);
  });

  it("does not refresh on the initial reading (no prior state)", () => {
    expect(shouldRefreshOnReconnect(true, undefined)).toBe(false);
  });

  it("does not refresh while staying online", () => {
    expect(shouldRefreshOnReconnect(true, true)).toBe(false);
  });

  it("does not refresh when going offline", () => {
    expect(shouldRefreshOnReconnect(false, true)).toBe(false);
  });

  it("does not refresh while staying offline", () => {
    expect(shouldRefreshOnReconnect(false, false)).toBe(false);
  });
});

describe("useServerConnection recovery", () => {
  it("refreshes on reconnect when no game is running", async () => {
    await install();
    await goOfflineThenOnline();
    expect(reload).toHaveBeenCalledOnce();
  });

  it("holds the refresh back while a game is running", async () => {
    await install();
    playingStore.playing = true;
    await nextTick();
    await goOfflineThenOnline();
    vi.advanceTimersByTime(60_000);
    expect(reload).not.toHaveBeenCalled();
  });

  it("refreshes once the player is left and the network goes quiet", async () => {
    await install();
    await playThroughABlip();

    playingStore.playing = false;
    await nextTick();
    // The player's teardown requests are still settling.
    expect(reload).not.toHaveBeenCalled();

    quiesce();
    expect(reload).toHaveBeenCalledOnce();
    // The cap must not fire a second reload behind it.
    vi.advanceTimersByTime(60_000);
    expect(reload).toHaveBeenCalledOnce();
  });

  it("refreshes on the cap when the network never goes quiet", async () => {
    await install();
    await playThroughABlip();

    playingStore.playing = false;
    await nextTick();
    vi.advanceTimersByTime(10_000);
    expect(reload).toHaveBeenCalledOnce();
  });

  it("drops a held-back refresh when the backend goes offline again", async () => {
    await install();
    await playThroughABlip();

    playingStore.playing = false;
    await nextTick();
    heartbeatStore.connected = false;
    await nextTick();
    quiesce();
    vi.advanceTimersByTime(60_000);
    expect(reload).not.toHaveBeenCalled();

    // The next recovery refreshes instead, now that nothing is running.
    heartbeatStore.connected = true;
    await nextTick();
    expect(reload).toHaveBeenCalledOnce();
  });

  it("does not refresh on a later play session when nothing was pending", async () => {
    await install();
    playingStore.playing = true;
    await nextTick();
    playingStore.playing = false;
    await nextTick();
    vi.advanceTimersByTime(60_000);
    expect(reload).not.toHaveBeenCalled();
  });
});
