import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import storeHeartbeat from "@/stores/heartbeat";
import { useWebpSupport } from ".";

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
