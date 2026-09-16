import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { useIsolatedLaunch } from "./index";

interface Intent {
  saveId: number | null;
}

function isIntent(value: unknown): value is Intent {
  return (
    typeof value === "object" &&
    value !== null &&
    "saveId" in value &&
    (value.saveId === null || typeof value.saveId === "number")
  );
}

const KEY = "player:7:ejs:launch";
const reload = vi.fn();
let originalLocation: Location;

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
  reload.mockClear();
  sessionStorage.clear();
});

describe("useIsolatedLaunch", () => {
  it("opens without an intent", () => {
    const launch = useIsolatedLaunch<Intent>("ejs", 7, isIntent);

    expect(launch.intent).toBeNull();
    expect(launch.relaunching.value).toBe(false);
  });

  it("keeps the intent and reloads the document", () => {
    const launch = useIsolatedLaunch<Intent>("ejs", 7, isIntent);

    expect(launch.relaunch({ saveId: 3 })).toBe(true);

    expect(launch.relaunching.value).toBe(true);
    expect(reload).toHaveBeenCalledOnce();
    expect(sessionStorage.getItem(KEY)).toBe('{"saveId":3}');
  });

  it("hands the intent to the reloaded view once", () => {
    useIsolatedLaunch<Intent>("ejs", 7, isIntent).relaunch({ saveId: 3 });

    expect(useIsolatedLaunch<Intent>("ejs", 7, isIntent).intent).toEqual({
      saveId: 3,
    });
    expect(useIsolatedLaunch<Intent>("ejs", 7, isIntent).intent).toBeNull();
  });

  // A second reload could not isolate the document either, so the view is
  // told to report the context instead of looping.
  it("refuses to reload again from the reloaded view", () => {
    useIsolatedLaunch<Intent>("ejs", 7, isIntent).relaunch({ saveId: 3 });
    reload.mockClear();
    const reloaded = useIsolatedLaunch<Intent>("ejs", 7, isIntent);

    expect(reloaded.relaunch({ saveId: 4 })).toBe(false);

    expect(reload).not.toHaveBeenCalled();
    expect(reloaded.relaunching.value).toBe(false);
  });

  it("keeps players and games apart", () => {
    useIsolatedLaunch<Intent>("ejs", 7, isIntent).relaunch({ saveId: 3 });

    expect(useIsolatedLaunch<Intent>("jsdos", 7, isIntent).intent).toBeNull();
    expect(useIsolatedLaunch<Intent>("ejs", 8, isIntent).intent).toBeNull();
    expect(useIsolatedLaunch<Intent>("ejs", 7, isIntent).intent).toEqual({
      saveId: 3,
    });
  });

  it.each([
    ["not JSON", "{"],
    ["another shape", JSON.stringify({ core: "snes9x" })],
  ])("drops a stored value that is %s", (_label, raw) => {
    sessionStorage.setItem(KEY, raw);

    expect(useIsolatedLaunch<Intent>("ejs", 7, isIntent).intent).toBeNull();
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
});
