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
const realStorage = window.sessionStorage;

/** Stand in for a browser that denies storage access outright. */
function blockStorage() {
  const denied = () => {
    throw new Error("storage is blocked");
  };
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    value: { getItem: denied, setItem: denied, removeItem: denied },
  });
}

function launch() {
  return useIsolatedLaunch<Intent>("ejs", 7, isIntent);
}

function setSecureContext(secure: boolean) {
  Object.defineProperty(window, "isSecureContext", {
    configurable: true,
    value: secure,
  });
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
  reload.mockClear();
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    value: realStorage,
  });
  sessionStorage.clear();
  setSecureContext(true);
});

describe("useIsolatedLaunch", () => {
  it("opens without an intent", () => {
    const first = launch();

    expect(first.intent).toBeNull();
    expect(first.relaunching.value).toBe(false);
  });

  it("keeps the intent and reloads the document", () => {
    const first = launch();

    expect(first.relaunch({ saveId: 3 })).toBe(true);

    expect(first.relaunching.value).toBe(true);
    expect(reload).toHaveBeenCalledOnce();
    expect(sessionStorage.getItem(KEY)).toBe('{"saveId":3}');
  });

  it("hands the intent to the reloaded view once", () => {
    launch().relaunch({ saveId: 3 });

    expect(launch().intent).toEqual({ saveId: 3 });
    expect(launch().intent).toBeNull();
  });

  // A second reload could not isolate the document either, so the view is
  // told to report the context instead of looping.
  it("refuses to reload again from the reloaded view", () => {
    launch().relaunch({ saveId: 3 });
    reload.mockClear();
    const reloaded = launch();

    expect(reloaded.relaunch({ saveId: 4 })).toBe(false);

    expect(reload).not.toHaveBeenCalled();
    expect(reloaded.relaunching.value).toBe(false);
  });

  // The headers cannot expose SharedArrayBuffer over plain HTTP, so the round
  // trip would only delay the same error.
  it("refuses to reload outside a secure context", () => {
    setSecureContext(false);
    const first = launch();

    expect(first.relaunch({ saveId: 3 })).toBe(false);

    expect(reload).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });

  it("refuses to reload when the selection cannot be kept", () => {
    const first = launch();
    blockStorage();

    expect(first.relaunch({ saveId: 3 })).toBe(false);

    expect(reload).not.toHaveBeenCalled();
    expect(first.relaunching.value).toBe(false);
  });

  // A player has to open even where storage access is denied outright.
  it("opens with no intent when storage cannot be read", () => {
    blockStorage();

    expect(launch().intent).toBeNull();
  });

  it("keeps players and games apart", () => {
    launch().relaunch({ saveId: 3 });

    expect(useIsolatedLaunch<Intent>("jsdos", 7, isIntent).intent).toBeNull();
    expect(useIsolatedLaunch<Intent>("ejs", 8, isIntent).intent).toBeNull();
    expect(launch().intent).toEqual({ saveId: 3 });
  });

  it.each([
    ["not JSON", "{"],
    ["another shape", JSON.stringify({ core: "snes9x" })],
  ])("drops a stored value that is %s", (_label, raw) => {
    sessionStorage.setItem(KEY, raw);

    expect(launch().intent).toBeNull();
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
});
