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

const push = vi.fn(() => Promise.resolve());
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

  it("lets its own departure through", async () => {
    let bound = false;
    const exit = usePlayerExit(() => bound);

    exit.leave("/rom/1");
    // The runtime cannot bind between leave() and the guard, but a guard that
    // re-checked the document would otherwise still be able to block the push.
    bound = true;
    expect(exit.guard({ fullPath: "/rom/1" })).toBe(true);

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(exit.guard({ fullPath: "/rom/1" })).toBe(false);
  });
});
