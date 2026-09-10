import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import storeHeartbeat from "@/stores/heartbeat";
import { toWebpUrl, useWebpSupport } from ".";

function setWebpTask(enabled: boolean) {
  const heartbeat = storeHeartbeat();
  heartbeat.value = {
    ...heartbeat.value,
    TASKS: {
      ...heartbeat.value.TASKS,
      ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP: enabled,
    },
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("useWebpSupport", () => {
  it("is off until the heartbeat says the conversion task runs", () => {
    const { supportsWebp, toWebp } = useWebpSupport();

    expect(supportsWebp.value).toBe(false);
    expect(toWebp("roms/1/2/cover/big.png")).toBe("roms/1/2/cover/big.png");
  });

  it("rewrites raster covers once the conversion task is enabled", () => {
    const { supportsWebp, toWebp } = useWebpSupport();
    setWebpTask(true);

    expect(supportsWebp.value).toBe(true);
    expect(toWebp("roms/1/2/cover/big.png")).toBe("roms/1/2/cover/big.webp");
    expect(toWebp("roms/1/2/cover/small.JPEG")).toBe(
      "roms/1/2/cover/small.webp",
    );
  });

  it("leaves a cover that is already webp alone", () => {
    const { toWebp } = useWebpSupport();
    setWebpTask(true);

    expect(toWebp("roms/1/2/cover/big.webp")).toBe("roms/1/2/cover/big.webp");
    expect(toWebp(null)).toBe("");
  });
});

describe("toWebpUrl", () => {
  // What the backend actually sends: `path_cover_large` and friends carry a
  // `?ts=<updated_at>` cache-buster, so an end-anchored match never fires.
  const COVER = "/assets/romm/resources/roms/1/2/cover/big.png?ts=2026-09-09";

  it("rewrites the extension behind a cache-busting query", () => {
    expect(toWebpUrl(COVER, true)).toBe(
      "/assets/romm/resources/roms/1/2/cover/big.webp?ts=2026-09-09",
    );
  });

  it("leaves the query itself alone", () => {
    expect(toWebpUrl("cover/big.jpg?v=a.png", true)).toBe(
      "cover/big.webp?v=a.png",
    );
  });

  it("rewrites a bare path too", () => {
    expect(toWebpUrl("cover/big.jpeg", true)).toBe("cover/big.webp");
  });

  it("passes the URL through when the server serves no webp", () => {
    expect(toWebpUrl(COVER, false)).toBe(COVER);
  });
});
