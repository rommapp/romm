import { afterEach, describe, expect, it, vi } from "vitest";

type ProbeImage = { onload: (() => void) | null; naturalWidth: number };

// Each test loads a fresh module, since the probe runs once per page.
async function loadWithDecoder(decodes: boolean) {
  vi.resetModules();
  vi.stubGlobal(
    "Image",
    class implements ProbeImage {
      onload: (() => void) | null = null;
      naturalWidth = 0;
      set src(_value: string) {
        if (!decodes) return;
        this.naturalWidth = 1;
        queueMicrotask(() => this.onload?.());
      }
    },
  );
  return import("@/utils/imageSupport");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("canRenderJxl", () => {
  it("turns true once the probe image decodes", async () => {
    const { canRenderJxl } = await loadWithDecoder(true);
    expect(canRenderJxl()).toBe(false);
    await Promise.resolve();
    expect(canRenderJxl()).toBe(true);
  });

  it("stays false when the browser cannot decode JPEG XL", async () => {
    const { canRenderJxl } = await loadWithDecoder(false);
    canRenderJxl();
    await Promise.resolve();
    expect(canRenderJxl()).toBe(false);
  });
});

describe("isRenderableImageExtension", () => {
  const exts = new Set(["png", "jxl"]);

  it("accepts listed formats and rejects unlisted ones", async () => {
    const { isRenderableImageExtension } = await loadWithDecoder(false);
    expect(isRenderableImageExtension("png", exts)).toBe(true);
    expect(isRenderableImageExtension("bmp", exts)).toBe(false);
  });

  it("gates JPEG XL on the probe", async () => {
    const { isRenderableImageExtension } = await loadWithDecoder(true);
    expect(isRenderableImageExtension("jxl", exts)).toBe(false);
    await Promise.resolve();
    expect(isRenderableImageExtension("jxl", exts)).toBe(true);
  });
});
