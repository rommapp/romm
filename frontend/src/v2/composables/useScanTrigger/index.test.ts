import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeScanning from "@/stores/scanning";
import { useScanTrigger } from "./index";

const { emit, connect, warning } = vi.hoisted(() => ({
  emit: vi.fn(),
  connect: vi.fn(),
  warning: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/services/socket", () => ({
  default: { connected: false, connect, emit },
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ warning }),
}));

describe("useScanTrigger", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    emit.mockClear();
    connect.mockClear();
    warning.mockClear();
  });

  it("flips the store, connects and emits one event per payload", () => {
    const { startScan } = useScanTrigger();

    const started = startScan([
      { platforms: [1], roms_ids: [5], type: "quick", apis: [] },
      { platforms: [2], roms_ids: [6], type: "quick", apis: [] },
    ]);

    expect(started).toBe(true);
    expect(storeScanning().scanning).toBe(true);
    expect(connect).toHaveBeenCalledOnce();
    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenCalledWith("scan", {
      platforms: [1],
      roms_ids: [5],
      type: "quick",
      apis: [],
    });
  });

  it("refuses while a scan is running and says so", () => {
    storeScanning().setScanning(true);
    const { startScan } = useScanTrigger();

    const started = startScan([{ type: "quick", roms_ids: [5], apis: [] }]);

    expect(started).toBe(false);
    expect(emit).not.toHaveBeenCalled();
    expect(warning).toHaveBeenCalledWith(
      "scan.scan-in-progress",
      expect.anything(),
    );
  });
});
