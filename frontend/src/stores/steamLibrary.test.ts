import { flushPromises } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import useSteamLibrary from "./steamLibrary";

vi.mock("@/services/api/user", () => ({
  default: { fetchSteamLibrary: vi.fn() },
}));
vi.mock("@/composables/useSocketEvent", () => ({ useSocketEvent: vi.fn() }));

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("steamLibrary", () => {
  beforeEach(() => {
    vi.mocked(userApi.fetchSteamLibrary)
      .mockReset()
      .mockResolvedValue({
        data: [220],
      } as never);
  });

  let library: ReturnType<typeof useSteamLibrary> | undefined;

  // A store left alive would still answer the next test's visibility events.
  afterEach(() => {
    library?.$dispose();
    setVisibility("visible");
  });

  it("loads the linked account's games and refetches when the tab returns", async () => {
    storeAuth().setCurrentUser(
      userFixture({ id: 1, steam_id: "76561197960287930" }),
    );
    library = useSteamLibrary();
    await flushPromises();

    expect(library.isLoaded).toBe(true);
    expect(library.owns(220)).toBe(true);

    vi.mocked(userApi.fetchSteamLibrary).mockResolvedValue({
      data: [400],
    } as never);
    setVisibility("hidden");
    setVisibility("visible");
    await flushPromises();

    expect(library.owns(220)).toBe(false);
    expect(library.owns(400)).toBe(true);
  });

  it("keeps the newest reply when an older one arrives late", async () => {
    let answerFirst: (value: unknown) => void = () => {};
    vi.mocked(userApi.fetchSteamLibrary)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          answerFirst = resolve;
        }) as never,
      )
      .mockResolvedValueOnce({ data: [400] } as never);
    storeAuth().setCurrentUser(
      userFixture({ id: 1, steam_id: "76561197960287930" }),
    );
    library = useSteamLibrary();
    void library.load();
    await flushPromises();

    answerFirst({ data: [220] });
    await flushPromises();

    expect(library.owns(400)).toBe(true);
    expect(library.owns(220)).toBe(false);
  });

  it("loads nothing without a linked account", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    library = useSteamLibrary();
    setVisibility("hidden");
    setVisibility("visible");
    await flushPromises();

    expect(userApi.fetchSteamLibrary).not.toHaveBeenCalled();
    expect(library.isLoaded).toBe(false);
  });
});
