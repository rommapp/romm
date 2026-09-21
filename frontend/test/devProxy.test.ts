import { describe, expect, it } from "vitest";
import { createRommDevProxy, resolveDevProxyTarget } from "../scripts/devProxy";

describe("resolveDevProxyTarget", () => {
  it("uses local backend when unset", () => {
    expect(resolveDevProxyTarget(undefined, "5000")).toEqual({
      target: "http://127.0.0.1:5000",
      remote: false,
    });
  });

  it("uses remote origin for https host", () => {
    expect(resolveDevProxyTarget("https://roms.example.com/", "5000")).toEqual({
      target: "https://roms.example.com",
      remote: true,
    });
  });

  it("treats localhost URL as non-remote proxy target", () => {
    expect(resolveDevProxyTarget("http://127.0.0.1:5000", "5000")).toEqual({
      target: "http://127.0.0.1:5000",
      remote: false,
    });
  });

  it("falls back with a warning on invalid URL", () => {
    const result = resolveDevProxyTarget("not-a-url", "5000");
    expect(result.target).toBe("http://127.0.0.1:5000");
    expect(result.remote).toBe(false);
    expect(result.warning).toMatch(/not a valid URL/);
  });
});

describe("createRommDevProxy", () => {
  it("includes library asset path", () => {
    const proxy = createRommDevProxy("https://roms.example.com", {
      remote: true,
    });
    expect(proxy["/assets/romm"]).toMatchObject({
      target: "https://roms.example.com",
      changeOrigin: true,
    });
  });
});
