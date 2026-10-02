import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { installFullscreenFallback } from "@/v2/utils/playerFullscreen";
import { usePlayerExit } from "./index";

const replace = vi.fn();
const locationReplace = vi.fn();

vi.mock("vue-router", () => ({
  useRouter: () => ({ replace }),
}));

function setIsolated(isolated: boolean) {
  vi.stubGlobal("crossOriginIsolated", isolated);
}

beforeEach(() => {
  vi.stubGlobal("location", { ...window.location, replace: locationReplace });
  locationReplace.mockReset();
});

describe("usePlayerExit", () => {
  it("leaves within the app when nothing binds the document", () => {
    const exit = usePlayerExit();

    exit.leave("/rom/1");

    expect(replace).toHaveBeenCalledWith("/rom/1");
    expect(locationReplace).not.toHaveBeenCalled();
    expect(exit.departing.value).toBe(false);
  });

  it("replaces the document when it is cross-origin isolated", async () => {
    setIsolated(true);
    const exit = usePlayerExit();

    exit.leave("/rom/1");
    await flushPromises();

    expect(locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(replace).not.toHaveBeenCalled();
  });

  it("replaces the document once a runtime is bound to it", async () => {
    const exit = usePlayerExit(() => true);

    exit.leave("/rom/1");
    await flushPromises();

    expect(locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(replace).not.toHaveBeenCalled();
  });

  it("lets a route departure through when nothing binds the document", async () => {
    const exit = usePlayerExit();

    await expect(exit.guard({ fullPath: "/platform/2" })).resolves.toBe(true);
    expect(locationReplace).not.toHaveBeenCalled();
  });

  it("turns a route departure into a full navigation when bound", async () => {
    setIsolated(true);
    const exit = usePlayerExit();

    void exit.guard({ fullPath: "/platform/2" });
    await flushPromises();

    expect(locationReplace).toHaveBeenCalledWith("/platform/2");
  });

  // An aborted Back makes the router traverse forward again, and that traversal
  // cancels a replace to the URL the Back already landed on.
  it("never settles a departure it turns into a full navigation", async () => {
    setIsolated(true);
    const exit = usePlayerExit();
    const settled = vi.fn();

    exit.guard({ fullPath: "/platform/2" }).then(settled, settled);
    await flushPromises();

    expect(locationReplace).toHaveBeenCalled();
    expect(settled).not.toHaveBeenCalled();
  });

  // What the departing document still owes runs while it is still there, since
  // the aborted navigation leaves the guards below it unrun.
  it("settles the document before replacing it", async () => {
    setIsolated(true);
    const settled: string[] = [];
    locationReplace.mockImplementation(() => settled.push("replace"));
    const exit = usePlayerExit(
      () => false,
      async () => {
        await Promise.resolve();
        settled.push("settle");
      },
    );

    void exit.guard({ fullPath: "/platform/2" });
    await flushPromises();

    expect(settled).toEqual(["settle", "replace"]);
  });

  it("leaves fullscreen before replacing the document", async () => {
    setIsolated(true);
    const dispose = installFullscreenFallback();
    const stage = document.body.appendChild(document.createElement("div"));
    await stage.requestFullscreen();
    let fullscreenAtReplace: Element | null | undefined;
    locationReplace.mockImplementation(() => {
      fullscreenAtReplace = document.fullscreenElement;
    });

    void usePlayerExit().guard({ fullPath: "/platform/2" });
    await flushPromises();

    expect(fullscreenAtReplace).toBeNull();
    dispose();
    stage.remove();
  });

  it("replaces the document even when settling fails", async () => {
    setIsolated(true);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const exit = usePlayerExit(
      () => false,
      () => Promise.reject(new Error("nope")),
    );

    void exit.guard({ fullPath: "/platform/2" });
    await flushPromises();

    expect(locationReplace).toHaveBeenCalledWith("/platform/2");
  });

  // The view arms an unload prompt while a game is up, and the exit it asked
  // for must not be what triggers it.
  it.each([
    [
      "an exit",
      (exit: ReturnType<typeof usePlayerExit>) => exit.leave("/rom/1"),
    ],
    [
      "a route departure",
      (exit: ReturnType<typeof usePlayerExit>) =>
        void exit.guard({ fullPath: "/rom/1" }),
    ],
  ])("announces %s that replaces the document", async (_label, act) => {
    setIsolated(true);
    const exit = usePlayerExit();

    act(exit);
    await flushPromises();

    expect(exit.departing.value).toBe(true);
  });
});
