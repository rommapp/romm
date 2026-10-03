import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick } from "vue";
import storePlaying from "@/stores/playing";
import { installSafeAreaViewport } from "./index";

let portrait = true;
let meta: HTMLMetaElement;

beforeEach(() => {
  portrait = true;
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query === "(orientation: portrait)" && portrait,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  meta = document.createElement("meta");
  meta.name = "viewport";
  meta.content = "width=device-width, initial-scale=1.0";
  document.head.appendChild(meta);
});

afterEach(() => {
  meta.remove();
  vi.unstubAllGlobals();
});

describe("installSafeAreaViewport", () => {
  it("covers the viewport in portrait and restores it on dispose", () => {
    const scope = effectScope();
    scope.run(installSafeAreaViewport);
    expect(meta.content).toBe(
      "width=device-width, initial-scale=1.0, viewport-fit=cover",
    );

    scope.stop();
    expect(meta.content).toBe("width=device-width, initial-scale=1.0");
  });

  it("keeps the default fit in landscape", () => {
    portrait = false;
    const scope = effectScope();
    scope.run(installSafeAreaViewport);
    expect(meta.content).toBe("width=device-width, initial-scale=1.0");
    scope.stop();
  });

  it("drops the cover while a player stage is active", async () => {
    const scope = effectScope();
    scope.run(installSafeAreaViewport);
    const store = storePlaying();

    store.setStageActive(true);
    await nextTick();
    expect(meta.content).toBe("width=device-width, initial-scale=1.0");

    store.setStageActive(false);
    await nextTick();
    expect(meta.content).toContain("viewport-fit=cover");
    scope.stop();
  });
});
