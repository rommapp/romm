import { flushPromises } from "@vue/test-utils";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { usePlayerExit } from "./index";

const replace = vi.fn();
const locationReplace = vi.fn();
let originalLocation: Location;

vi.mock("vue-router", () => ({
  useRouter: () => ({ replace }),
}));

function setIsolated(isolated: boolean) {
  Object.defineProperty(window, "crossOriginIsolated", {
    configurable: true,
    value: isolated,
  });
}

beforeAll(() => {
  originalLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, replace: locationReplace },
  });
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

afterEach(() => {
  replace.mockClear();
  locationReplace.mockReset();
  setIsolated(false);
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

    await expect(exit.guard({ fullPath: "/platform/2" })).resolves.toBe(false);
    expect(locationReplace).toHaveBeenCalledWith("/platform/2");
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

    await exit.guard({ fullPath: "/platform/2" });

    expect(settled).toEqual(["settle", "replace"]);
  });

  it("replaces the document even when settling fails", async () => {
    setIsolated(true);
    const error = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const exit = usePlayerExit(
      () => false,
      () => Promise.reject(new Error("nope")),
    );

    await exit.guard({ fullPath: "/platform/2" });

    expect(locationReplace).toHaveBeenCalledWith("/platform/2");
    error.mockRestore();
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
        exit.guard({ fullPath: "/rom/1" }),
    ],
  ])("announces %s that replaces the document", async (_label, act) => {
    setIsolated(true);
    const exit = usePlayerExit();

    act(exit);
    await flushPromises();

    expect(exit.departing.value).toBe(true);
  });
});
