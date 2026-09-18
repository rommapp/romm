import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import streamingApi, { type JoinableSession } from "@/services/api/streaming";
import { useStreamingStore } from "@/stores/streaming";

vi.mock("@/services/api/streaming", () => ({
  default: {
    listJoinableSessions: vi.fn(),
    saveAndExit: vi.fn(),
    saveAndExitKeepalive: vi.fn(),
  },
}));

describe("platformCapabilities disc flags", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("maps the backend disc flags to camelCase", () => {
    const store = useStreamingStore();
    store.config = {
      enabled: true,
      emulator_labels: {},
      containers: [
        {
          platform: "dc",
          host: "http://x",
          label: "RetroArch",
          emulator: "retroarch",
          supports_memory_cards: false,
          supports_save_picker: false,
          capabilities: {
            max_slots: 0,
            has_autosave: true,
            autosave_slot: 10,
            has_memory_card: false,
            supports_disc_swap: true,
            has_manual_disc_swap: false,
          },
        },
      ],
    };
    expect(store.platformCapabilities("dc").supportsDiscSwap).toBe(true);
    expect(store.platformCapabilities("dc").hasManualDiscSwap).toBe(false);
  });

  it("reports no disc swap for an unconfigured platform", () => {
    const store = useStreamingStore();
    expect(store.platformCapabilities("dc").supportsDiscSwap).toBe(false);
  });
});

describe("emulator labels", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("names an emulator by the label the backend ships", () => {
    const store = useStreamingStore();
    store.config = {
      enabled: true,
      containers: [],
      emulator_labels: { play: "Play!" },
    };
    expect(store.emulatorLabel("play")).toBe("Play!");
  });

  it("names an emulator configured in another case", () => {
    const store = useStreamingStore();
    store.config = {
      enabled: true,
      containers: [],
      emulator_labels: { play: "Play!" },
    };
    expect(store.emulatorLabel("Play")).toBe("Play!");
  });

  it("falls back to the id for an emulator it was told nothing about", () => {
    const store = useStreamingStore();
    expect(store.emulatorLabel("snes9x")).toBe("snes9x");
  });
});

describe("joinable sessions", () => {
  const listJoinableSessions =
    streamingApi.listJoinableSessions as unknown as Mock;

  function sessions(romId: number) {
    const session: JoinableSession = {
      container: "ps2-1",
      label: "PCSX2",
      platform: "ps2",
      rom_id: romId,
      rom_name: "Game",
      host_username: "ana",
      claimed_at: "2026-01-01T00:00:00Z",
      platform_id: 1,
      platform_display_name: "PlayStation 2",
      path_cover_small: null,
      path_cover_large: null,
      url_cover: null,
    };
    return { data: { sessions: [session] } };
  }

  beforeEach(() => {
    setActivePinia(createPinia());
    listJoinableSessions.mockReset();
    listJoinableSessions.mockResolvedValue(sessions(7));
  });

  it("collapses concurrent callers into one request", async () => {
    // A virtualised gallery mounts many action surfaces at once; one request
    // each would be a storm, and the last response to land would win.
    const store = useStreamingStore();

    await Promise.all([
      store.fetchJoinableSessions(),
      store.fetchJoinableSessions(),
      store.fetchJoinableSessions(),
    ]);

    expect(listJoinableSessions).toHaveBeenCalledTimes(1);
    expect(store.joinableForRom(7)?.host_username).toBe("ana");
  });

  it("serves a second caller from the freshness window, and refetches when forced", async () => {
    const store = useStreamingStore();

    await store.fetchJoinableSessions();
    await store.fetchJoinableSessions();
    expect(listJoinableSessions).toHaveBeenCalledTimes(1);

    await store.fetchJoinableSessions(true);
    expect(listJoinableSessions).toHaveBeenCalledTimes(2);
  });

  it("drops a session the caller found to be gone", async () => {
    const store = useStreamingStore();
    await store.fetchJoinableSessions();

    store.forgetJoinableSession(7);

    expect(store.joinableForRom(7)).toBeNull();
  });

  it("keeps the last known list when a refresh fails", async () => {
    const store = useStreamingStore();
    await store.fetchJoinableSessions();

    listJoinableSessions.mockRejectedValueOnce(new Error("offline"));
    await store.fetchJoinableSessions(true);

    expect(store.joinableForRom(7)?.host_username).toBe("ana");
  });
});

describe("save-and-exit", () => {
  const saveAndExit = streamingApi.saveAndExit as unknown as Mock;
  const saveAndExitKeepalive =
    streamingApi.saveAndExitKeepalive as unknown as Mock;

  beforeEach(() => {
    setActivePinia(createPinia());
    saveAndExit.mockReset();
    saveAndExitKeepalive.mockReset();
  });

  it("names the claim it saves", async () => {
    saveAndExit.mockResolvedValue({ data: { released: true, saved: true } });

    await useStreamingStore().saveAndExit(
      "ps2",
      0,
      false,
      "ps2-1",
      "2026-01-01T00:00:00Z",
    );

    expect(saveAndExit).toHaveBeenCalledWith(
      "ps2",
      0,
      false,
      "ps2-1",
      "2026-01-01T00:00:00Z",
    );
  });

  it("names the claim it saves on unload", () => {
    saveAndExitKeepalive.mockResolvedValue(new Response());

    useStreamingStore().saveAndExitKeepalive(
      "ps2",
      0,
      "ps2-1",
      "2026-01-01T00:00:00Z",
    );

    expect(saveAndExitKeepalive).toHaveBeenCalledWith(
      "ps2",
      0,
      "ps2-1",
      "2026-01-01T00:00:00Z",
    );
  });
});
