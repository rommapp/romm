import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
// Re-imported per case below, but the bases are the same strings either way.
import { CDN_BASE as CDN, LOCAL_BASE as LOCAL } from "./jsDosRuntime";

const mocks = vi.hoisted(() => ({
  isJsResource: vi.fn(),
  loadScript: vi.fn(),
}));

vi.mock("@/v2/utils/scriptLoader", () => ({
  isJsResource: mocks.isJsResource,
  loadScript: mocks.loadScript,
}));

// The loader is a module-level singleton, so each case starts from a document
// that has never loaded it.
async function loadFresh() {
  vi.resetModules();
  return import("./jsDosRuntime");
}

// Intercepted rather than inserted: a real <link> would have the test
// environment go out and fetch the stylesheet.
beforeAll(() => {
  vi.spyOn(document.head, "appendChild").mockImplementation((node) => node);
});

afterAll(() => {
  vi.restoreAllMocks();
});

function stylesheets(): string[] {
  return vi
    .mocked(document.head.appendChild)
    .mock.calls.map(([node]) => (node as Element).getAttribute("href") ?? "");
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isJsResource.mockResolvedValue(true);
  mocks.loadScript.mockResolvedValue(undefined);
});

describe("loadJsDosRuntime", () => {
  it("serves the runtime from the local assets when they are present", async () => {
    const { loadJsDosRuntime } = await loadFresh();

    await expect(loadJsDosRuntime()).resolves.toBe(LOCAL);
    expect(mocks.loadScript).toHaveBeenCalledWith(`${LOCAL}/js-dos.js`);
    expect(stylesheets()).toContain(`${LOCAL}/js-dos.css`);
  });

  // Slim images and the Vite dev server ship no local copy, and both answer a
  // missing asset with 200 + index.html rather than a 404.
  it("falls back to the pinned CDN when the local path serves no JavaScript", async () => {
    mocks.isJsResource.mockResolvedValue(false);
    const { loadJsDosRuntime } = await loadFresh();

    await expect(loadJsDosRuntime()).resolves.toBe(CDN);
    expect(mocks.loadScript).toHaveBeenCalledWith(`${CDN}/js-dos.js`);
    expect(stylesheets()).toContain(`${CDN}/js-dos.css`);
  });

  // Views can mount in the same document either side of the first load
  // resolving, and neither order may inject a second runtime.
  it("injects once however many views ask", async () => {
    const { loadJsDosRuntime } = await loadFresh();

    const concurrent = await Promise.all([
      loadJsDosRuntime(),
      loadJsDosRuntime(),
    ]);
    await expect(loadJsDosRuntime()).resolves.toBe(LOCAL);

    expect(concurrent).toEqual([LOCAL, LOCAL]);
    expect(mocks.loadScript).toHaveBeenCalledOnce();
  });

  it("lets a later view retry after a failed load", async () => {
    mocks.loadScript.mockRejectedValueOnce(new Error("network"));
    const { loadJsDosRuntime } = await loadFresh();

    await expect(loadJsDosRuntime()).rejects.toThrow("network");
    await expect(loadJsDosRuntime()).resolves.toBe(LOCAL);

    expect(mocks.loadScript).toHaveBeenCalledTimes(2);
  });
});
