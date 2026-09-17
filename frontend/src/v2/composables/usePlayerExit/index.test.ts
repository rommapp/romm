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

const push = vi.fn();
const locationReplace = vi.fn();
let originalLocation: Location;

vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
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
  push.mockClear();
  locationReplace.mockClear();
  setIsolated(false);
});

describe("usePlayerExit", () => {
  it("leaves within the app when nothing binds the document", () => {
    const exit = usePlayerExit();

    exit.leave("/rom/1");

    expect(push).toHaveBeenCalledWith("/rom/1");
    expect(locationReplace).not.toHaveBeenCalled();
    expect(exit.departing.value).toBe(false);
  });

  it("replaces the document when it is cross-origin isolated", () => {
    setIsolated(true);
    const exit = usePlayerExit();

    exit.leave("/rom/1");

    expect(locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(push).not.toHaveBeenCalled();
  });

  it("replaces the document once a runtime is bound to it", () => {
    const exit = usePlayerExit(() => true);

    exit.leave("/rom/1");

    expect(locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(push).not.toHaveBeenCalled();
  });

  it("lets a route departure through when nothing binds the document", () => {
    const exit = usePlayerExit();

    expect(exit.guard({ fullPath: "/platform/2" })).toBe(true);
    expect(locationReplace).not.toHaveBeenCalled();
  });

  it("turns a route departure into a full navigation when bound", () => {
    setIsolated(true);
    const exit = usePlayerExit();

    expect(exit.guard({ fullPath: "/platform/2" })).toBe(false);
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
        exit.guard({ fullPath: "/rom/1" }),
    ],
  ])("announces %s that replaces the document", (_label, act) => {
    setIsolated(true);
    const exit = usePlayerExit();

    act(exit);

    expect(exit.departing.value).toBe(true);
  });
});
