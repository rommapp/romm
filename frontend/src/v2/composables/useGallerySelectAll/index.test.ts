import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import { useGallerySelectAll } from "@/v2/composables/useGallerySelectAll";
import storeGalleryRoms, {
  SELECT_ALL_PAGE_SIZE,
} from "@/v2/stores/galleryRoms";
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

// A gallery context is required for the whole-result fetch; Search is
// the lightest one to fake.
function galleryContext() {
  const galleryRoms = storeGalleryRoms();
  galleryRoms.currentSearch = true;
  return galleryRoms;
}

describe("useGallerySelectAll", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Un-stub the console.error spy from the failure-path test.
    vi.restoreAllMocks();
  });

  it("selects the whole filtered result, not just the loaded windows", async () => {
    const galleryRoms = galleryContext();
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
      limit: SELECT_ALL_PAGE_SIZE,
      offset: 0,
      withCharIndex: false,
      withFilterValues: false,
      withRomIdIndex: false,
      withTotal: false,
    });
  });

  it("merges the loaded roms before the whole-result fetch resolves", async () => {
    const galleryRoms = galleryContext();
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

  it("fetches the whole result while the bootstrap is still pending", async () => {
    // Loaded windows can resolve before the metadata bootstrap fills
    // `romIdIndex`; select-all must not mistake them for full coverage.
    const galleryRoms = galleryContext();
    const selection = storeGallerySelection();
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));
    getRoms.mockResolvedValue(resultPage([rom(1), rom(2), rom(3), rom(4)]));

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3, 4]);
  });

  it("skips the fetch when the whole result is already selected", async () => {
    const galleryRoms = galleryContext();
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
    const galleryRoms = galleryContext();
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

  it("re-arms the running fetch when re-triggered after a clear", async () => {
    const galleryRoms = galleryContext();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2, 3];
    galleryRoms.byPosition.set(0, rom(1));
    const d = deferred();
    getRoms.mockReturnValue(d.promise);

    const { selectAll } = useGallerySelectAll();
    const first = selectAll();
    selection.clear();
    // The re-trigger must not need a second fetch: the in-flight one is
    // revalidated for the fresh intent.
    const second = selectAll();
    d.resolve(resultPage([rom(1), rom(2), rom(3)]));
    await Promise.all([first, second]);

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3]);
  });

  it("keeps a rom deselected during the fetch out of the merge", async () => {
    const galleryRoms = galleryContext();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2, 3];
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));
    const d = deferred();
    getRoms.mockReturnValue(d.promise);

    const { selectAll } = useGallerySelectAll();
    const done = selectAll();
    selection.toggle(rom(1), 0);
    d.resolve(resultPage([rom(1), rom(2), rom(3)]));
    await done;

    expect(selection.ids.sort((a, b) => a - b)).toEqual([2, 3]);
  });

  it("falls back to loaded-only coverage without a rom id index", async () => {
    // Surfaces that opt out of the sidecar (Settings "Missing" tab)
    // finish the bootstrap with an empty index.
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.metadataLoaded = true;
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

  it("stays loaded-only on opt-out surfaces even before any window lands", async () => {
    // Like the Missing tab: no gallery context, bootstrap resolved with
    // no id index, rows still skeletons.
    const galleryRoms = storeGalleryRoms();
    galleryRoms.metadataLoaded = true;

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
  });

  it("does nothing on an empty filtered result", async () => {
    const galleryRoms = galleryContext();
    const selection = storeGallerySelection();
    galleryRoms.metadataLoaded = true;

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
    expect(selection.count).toBe(0);
  });

  it("surfaces a snackbar when the whole-result fetch fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const galleryRoms = galleryContext();
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
    const galleryRoms = galleryContext();
    const selection = storeGallerySelection();
    galleryRoms.romIdIndex = [1, 2];

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");

    selection.selectMany([rom(1)]);
    expect(selectionState.value).toBe("some");

    selection.selectMany([rom(2)]);
    expect(selectionState.value).toBe("all");
  });

  it("reports off over an empty result despite out-of-filter picks", () => {
    galleryContext();
    const selection = storeGallerySelection();
    selection.selectMany([rom(9)]);

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");
  });
});
