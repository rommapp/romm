import { describe, expect, it } from "vitest";
import { createRommDevProxy, resolveDevProxyTarget } from "../scripts/devProxy";

describe("resolveDevProxyTarget", () => {
  it("uses local backend when unset", () => {
    expect(resolveDevProxyTarget(undefined, "5000")).toEqual({
      target: "http://127.0.0.1:5000",
      remote: false,
      proxyAssets: false,
    });
  });

  it("uses remote origin for https host", () => {
    expect(resolveDevProxyTarget("https://roms.example.com/", "5000")).toEqual({
      target: "https://roms.example.com",
      remote: true,
      proxyAssets: true,
    });
  });

  it.each([
    ["http://127.0.0.1:5001", "http://127.0.0.1:5001"],
    ["http://localhost:5001/", "http://localhost:5001"],
    ["http://[::1]:5001", "http://[::1]:5001"],
  ])(
    "sets proxyAssets true for explicit loopback DEV_PROXY_TARGET (%s)",
    (raw, origin) => {
      expect(resolveDevProxyTarget(raw, "5000")).toEqual({
        target: origin,
        remote: false,
        proxyAssets: true,
      });
    },
  );

  it("falls back with a warning on invalid URL", () => {
    const result = resolveDevProxyTarget("not-a-url", "5000");
    expect(result.target).toBe("http://127.0.0.1:5000");
    expect(result.remote).toBe(false);
    expect(result.proxyAssets).toBe(false);
    expect(result.warning).toMatch(/not a valid URL/);
  });
});

describe("createRommDevProxy", () => {
  it("registers /assets/romm when proxyAssets is true (remote host)", () => {
    const proxy = createRommDevProxy("https://roms.example.com", {
      remote: true,
      proxyAssets: true,
    });
    expect(proxy["/assets/romm"]).toMatchObject({
      target: "https://roms.example.com",
      changeOrigin: true,
    });
  });

  it("registers /assets/romm when proxyAssets is true but remote is false", () => {
    const proxy = createRommDevProxy("http://127.0.0.1:5001", {
      remote: false,
      proxyAssets: true,
    });
    expect(proxy["/assets/romm"]).toMatchObject({
      target: "http://127.0.0.1:5001",
      changeOrigin: false,
    });
  });

  it("omits /assets/romm when proxyAssets is false", () => {
    const proxy = createRommDevProxy("http://127.0.0.1:5000", {
      remote: false,
      proxyAssets: false,
    });
    expect(proxy["/assets/romm"]).toBeUndefined();
  });
});
