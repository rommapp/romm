import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlayHistoryExportSection from "./PlayHistoryExportSection.vue";

const { exportBackloggdCsv, snackbarError, downloadBlob } = vi.hoisted(() => ({
  exportBackloggdCsv: vi.fn(),
  snackbarError: vi.fn(),
  downloadBlob: vi.fn(),
}));

vi.mock("@/services/api/export", () => ({
  default: { exportBackloggdCsv },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));

vi.mock("@/v2/utils/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/v2/utils/download")>()),
  downloadBlob,
}));

function clickExport() {
  const wrapper = mount(PlayHistoryExportSection);
  return { wrapper, click: () => wrapper.get("button").trigger("click") };
}

describe("PlayHistoryExportSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("downloads the CSV under the filename the server asks for", async () => {
    const blob = new Blob(["Game\n"], { type: "text/csv" });
    exportBackloggdCsv.mockResolvedValue({
      data: blob,
      headers: {
        "content-disposition":
          'attachment; filename="romm-backloggd-2026-01-02.csv"',
      },
    });

    const { click } = clickExport();
    await click();
    await flushPromises();

    expect(downloadBlob).toHaveBeenCalledWith(
      blob,
      "romm-backloggd-2026-01-02.csv",
    );
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("falls back to a default filename when the header is missing", async () => {
    exportBackloggdCsv.mockResolvedValue({ data: new Blob([]), headers: {} });

    const { click } = clickExport();
    await click();
    await flushPromises();

    expect(downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      "romm-backloggd.csv",
    );
  });

  it("refuses a second click while the first export is in flight", async () => {
    let release: (value: unknown) => void = () => {};
    exportBackloggdCsv.mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    const { wrapper, click } = clickExport();
    await click();
    await click();

    expect(exportBackloggdCsv).toHaveBeenCalledTimes(1);
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();

    release({ data: new Blob([]), headers: {} });
    await flushPromises();

    expect(wrapper.get("button").attributes("disabled")).toBeUndefined();
  });

  it("surfaces a failed export and downloads nothing", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    exportBackloggdCsv.mockRejectedValue(new Error("boom"));

    const { click } = clickExport();
    await click();
    await flushPromises();

    expect(downloadBlob).not.toHaveBeenCalled();
    expect(snackbarError).toHaveBeenCalledWith(
      "settings.play-history-export-failed",
      expect.anything(),
    );
  });
});
