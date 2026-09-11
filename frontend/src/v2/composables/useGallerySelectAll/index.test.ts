import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { useGallerySelectAll } from "@/v2/composables/useGallerySelectAll";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

const { getRoms, snackbarError } = vi.hoisted(() => ({
  getRoms: vi.fn(),
  snackbarError: vi.fn(),
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRoms },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: snackbarError,
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function rom(id: number): SimpleRom {
  return { id, name: `Game ${id}`, platform_id: 1 } as SimpleRom;
}

function resultPage(items: SimpleRom[]) {
  return {
    data: { total: null, items, char_index: {}, rom_id_index: [] },
  };
}

interface Deferred {
  promise: Promise<unknown>;
  resolve: (value: unknown) => void;
}

function deferred(): Deferred {
  let resolve!: (value: unknown) => void;
  const promise = new Promise<unknown>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe("useGallerySelectAll", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("selects the whole filtered result, not just the loaded windows", async () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2, 3, 4];
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));
    getRoms.mockResolvedValue(resultPage([rom(1), rom(2), rom(3), rom(4)]));

    const { selectAll, allSelected } = useGallerySelectAll();
    await selectAll();

    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3, 4]);
    expect(allSelected.value).toBe(true);
    // One whole-result request, sidecar aggregations off.
    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(getRoms.mock.calls[0][0]).toMatchObject({
      limit: 10_000,
      offset: 0,
      withCharIndex: false,
      withFilterValues: false,
      withRomIdIndex: false,
      withTotal: false,
    });
  });

  it("merges the loaded roms before the whole-result fetch resolves", async () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2, 3];
    galleryRoms.byPosition.set(0, rom(1));
    const d = deferred();
    getRoms.mockReturnValue(d.promise);

    const { selectAll } = useGallerySelectAll();
    const done = selectAll();
    expect(selection.ids).toEqual([1]);

    d.resolve(resultPage([rom(1), rom(2), rom(3)]));
    await done;
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3]);
  });

  it("skips the fetch when the whole result is already selected", async () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2];
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));
    selection.selectMany([rom(1), rom(2)]);

    const { selectAll, selectionState } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
    expect(selectionState.value).toBe("all");
  });

  it("drops a late result when the selection was cleared mid-fetch", async () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2];
    galleryRoms.byPosition.set(0, rom(1));
    const d = deferred();
    getRoms.mockReturnValue(d.promise);

    const { selectAll } = useGallerySelectAll();
    const done = selectAll();
    selection.clear();
    d.resolve(resultPage([rom(1), rom(2)]));
    await done;

    expect(selection.count).toBe(0);
  });

  it("falls back to loaded-only coverage without a rom id index", async () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));

    const { selectAll, allSelected } = useGallerySelectAll();
    await selectAll();

    // The instant merge already covers everything the surface knows
    // about, so no whole-result fetch is issued.
    expect(getRoms).not.toHaveBeenCalled();
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2]);
    expect(allSelected.value).toBe(true);
  });

  it("surfaces a snackbar when the whole-result fetch fails", async () => {
    const galleryRoms = storeGalleryRoms();
    galleryRoms.romIdIndex = [1, 2];
    getRoms.mockRejectedValue(new Error("boom"));

    const { selectAll, selectingAll } = useGallerySelectAll();
    await selectAll();
    await flushPromises();

    expect(snackbarError).toHaveBeenCalledWith(
      "gallery.selection-select-all-fail",
    );
    expect(selectingAll.value).toBe(false);
  });

  it("reports tri-state coverage for the header checkbox", () => {
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2];

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");

    selection.selectMany([rom(1)]);
    expect(selectionState.value).toBe("some");

    selection.selectMany([rom(2)]);
    expect(selectionState.value).toBe("all");
  });
});
