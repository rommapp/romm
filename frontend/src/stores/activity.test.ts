import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ActivityEntry } from "@/services/api/activity";
import storeActivity from "@/stores/activity";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";

const { get, handlers } = vi.hoisted(() => ({
  get: vi.fn(),
  handlers: new Map<string, (data: unknown) => void>(),
}));

vi.mock("@/services/api", () => ({
  default: { get, post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/services/socket", () => ({
  default: {
    connected: true,
    connect: vi.fn(),
    on: (event: string, handler: (data: unknown) => void) =>
      handlers.set(event, handler),
  },
}));

function entry(overrides: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    user_id: 2,
    username: "player",
    avatar_path: "",
    rom_id: 10,
    rom_name: "Game",
    rom_cover_path: "",
    screenshot_path: "",
    platform_slug: "gba",
    platform_name: "Game Boy Advance",
    device_id: "deck",
    device_type: "web",
    started_at: "2026-10-04T12:00:00Z",
    ...overrides,
  };
}

describe("activity store socket events", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    handlers.clear();
    get.mockReset();
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    storeActivity().initSocket();
  });

  it("adds, replaces and clears a session", () => {
    const store = storeActivity();

    handlers.get("activity:update")!(entry());
    handlers.get("activity:update")!(entry({ rom_id: 11 }));
    expect(store.activities.map((a) => a.rom_id)).toEqual([11]);

    handlers.get("activity:clear")!({
      user_id: 2,
      device_id: "deck",
      rom_id: 11,
    });
    expect(store.activities).toEqual([]);
  });

  it("re-lists sessions when the current user's permissions change", async () => {
    const store = storeActivity();
    handlers.get("activity:update")!(entry());
    get.mockResolvedValue({ data: [] });

    handlers.get("permissions:changed")!({ user_id: 1 });
    await vi.waitFor(() => expect(store.activities).toEqual([]));

    expect(get).toHaveBeenCalledWith("/activity");
  });

  it("ignores another user's permission change", () => {
    handlers.get("permissions:changed")!({ user_id: 3 });

    expect(get).not.toHaveBeenCalled();
  });

  it("keeps a session when a late clear names its previous game", () => {
    const store = storeActivity();
    handlers.get("activity:update")!(entry({ rom_id: 11 }));

    handlers.get("activity:clear")!({
      user_id: 2,
      device_id: "deck",
      rom_id: 10,
    });

    expect(store.activities.map((a) => a.rom_id)).toEqual([11]);
  });

  it("re-lists when an event lands while the list is in flight", async () => {
    const store = storeActivity();
    get
      .mockImplementationOnce(() => {
        handlers.get("activity:update")!(entry({ rom_id: 11 }));
        return Promise.resolve({ data: [] });
      })
      .mockResolvedValueOnce({ data: [entry({ rom_id: 11 })] });

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(2);
    expect(store.activities.map((a) => a.rom_id)).toEqual([11]);
  });

  it("settles for the last list when events keep landing", async () => {
    const store = storeActivity();
    get.mockImplementation(() => {
      handlers.get("activity:update")!(entry({ rom_id: 11 }));
      return Promise.resolve({ data: [entry({ rom_id: 12 })] });
    });

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(3);
    expect(store.activities.map((a) => a.rom_id)).toEqual([12]);
    expect(store.initialized).toBe(true);
  });

  it("asks again rather than racing when a list is requested mid-request", async () => {
    const store = storeActivity();
    let answerFirst = (_: { data: ActivityEntry[] }) => {};
    get
      .mockImplementationOnce(
        () => new Promise((resolve) => (answerFirst = resolve)),
      )
      .mockResolvedValueOnce({ data: [] });

    const first = store.fetchAll();
    await store.fetchAll();
    expect(get).toHaveBeenCalledTimes(1);
    answerFirst({ data: [entry()] });
    await first;

    expect(get).toHaveBeenCalledTimes(2);
    expect(store.activities).toEqual([]);
  });

  it("recovers when the request after a dropped answer fails", async () => {
    const store = storeActivity();
    get
      .mockImplementationOnce(() => {
        void store.fetchAll();
        return Promise.resolve({ data: [entry({ rom_id: 11 })] });
      })
      .mockRejectedValueOnce(new Error("blip"))
      .mockResolvedValueOnce({ data: [entry({ rom_id: 12 })] });

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(3);
    expect(store.activities.map((a) => a.rom_id)).toEqual([12]);
    expect(store.initialized).toBe(true);
  });

  it("makes a list asked for while the running request fails", async () => {
    const store = storeActivity();
    get
      .mockImplementationOnce(() => {
        void store.fetchAll();
        return Promise.reject(new Error("blip"));
      })
      .mockResolvedValueOnce({ data: [entry({ rom_id: 12 })] });

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(2);
    expect(store.activities.map((a) => a.rom_id)).toEqual([12]);
    expect(store.initialized).toBe(true);
  });

  it("makes a list asked for after the event retries run out", async () => {
    const store = storeActivity();
    get
      .mockImplementationOnce(() => {
        handlers.get("activity:update")!(entry());
        return Promise.resolve({ data: [] });
      })
      .mockImplementationOnce(() => {
        handlers.get("activity:update")!(entry());
        return Promise.resolve({ data: [] });
      })
      .mockImplementationOnce(() => {
        void store.fetchAll();
        return Promise.resolve({ data: [entry({ rom_id: 11 })] });
      })
      .mockResolvedValueOnce({ data: [entry({ rom_id: 12 })] });

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(4);
    expect(store.activities.map((a) => a.rom_id)).toEqual([12]);
  });

  it("asks once when a plain request fails", async () => {
    const store = storeActivity();
    vi.spyOn(console, "error").mockImplementation(() => {});
    get.mockRejectedValue(new Error("down"));

    await store.fetchAll();

    expect(get).toHaveBeenCalledTimes(1);
    expect(store.initialized).toBe(false);
    expect(store.fetching).toBe(false);
  });

  it("re-lists sessions when the server asks everyone to refresh", async () => {
    const store = storeActivity();
    handlers.get("activity:update")!(entry());
    get.mockResolvedValue({ data: [] });

    handlers.get("activity:refresh")!({});
    await vi.waitFor(() => expect(store.activities).toEqual([]));
  });

  it("ignores a refresh when signed out", () => {
    storeAuth().setCurrentUser(null);

    handlers.get("activity:refresh")!({});

    expect(get).not.toHaveBeenCalled();
  });
});
