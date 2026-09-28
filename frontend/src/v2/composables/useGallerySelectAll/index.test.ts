import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  return { data: { items } };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

/** Gallery context (Search is the lightest to fake) with a known id
 * index and pre-loaded windows. Omit `ids` for a pending bootstrap. */
function setupGallery({
  ids,
  loaded = [],
}: { ids?: number[]; loaded?: SimpleRom[] } = {}) {
  const galleryRoms = storeGalleryRoms();
  galleryRoms.currentSearch = true;
  if (ids) {
    galleryRoms.romIdIndex = ids;
    galleryRoms.metadataLoaded = true;
  }
  loaded.forEach((r, position) => galleryRoms.byPosition.set(position, r));
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
    setupGallery({ ids: [1, 2, 3, 4], loaded: [rom(1), rom(2)] });
    const selection = storeGallerySelection();
    getRoms.mockResolvedValue(resultPage([rom(1), rom(2), rom(3), rom(4)]));

    const { selectAll, allSelected } = useGallerySelectAll();
    await selectAll();

    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3, 4]);
    expect(allSelected.value).toBe(true);
    expect(getRoms).toHaveBeenCalledTimes(1);
  });

  it("merges the loaded roms before the whole-result fetch resolves", async () => {
    setupGallery({ ids: [1, 2, 3], loaded: [rom(1)] });
    const selection = storeGallerySelection();
    const d = deferred<ReturnType<typeof resultPage>>();
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
    setupGallery({ loaded: [rom(1), rom(2)] });
    const selection = storeGallerySelection();
    getRoms.mockResolvedValue(resultPage([rom(1), rom(2), rom(3), rom(4)]));

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3, 4]);
  });

  it("skips the fetch when the whole result is already selected", async () => {
    setupGallery({ ids: [1, 2], loaded: [rom(1), rom(2)] });
    const selection = storeGallerySelection();
    selection.selectMany([rom(1), rom(2)]);

    const { selectAll, selectionState } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
    expect(selectionState.value).toBe("all");
  });

  it("drops a late result when the selection was cleared mid-fetch", async () => {
    setupGallery({ ids: [1, 2], loaded: [rom(1)] });
    const selection = storeGallerySelection();
    const d = deferred<ReturnType<typeof resultPage>>();
    getRoms.mockReturnValue(d.promise);

    const { selectAll } = useGallerySelectAll();
    const done = selectAll();
    selection.clear();
    d.resolve(resultPage([rom(1), rom(2)]));
    await done;

    expect(selection.count).toBe(0);
  });

  it("supersedes the running fetch when re-triggered after a clear", async () => {
    setupGallery({ ids: [1, 2, 3], loaded: [rom(1)] });
    const selection = storeGallerySelection();
    const first = deferred<ReturnType<typeof resultPage>>();
    const second = deferred<ReturnType<typeof resultPage>>();
    getRoms
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { selectAll } = useGallerySelectAll();
    const run1 = selectAll();
    selection.clear();
    const run2 = selectAll();
    first.resolve(resultPage([rom(1), rom(2), rom(3)]));
    second.resolve(resultPage([rom(1), rom(2), rom(3)]));
    await Promise.all([run1, run2]);

    // The superseded run's result is discarded; the fresh run merges.
    expect(getRoms).toHaveBeenCalledTimes(2);
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2, 3]);
  });

  it("keeps a rom deselected during the fetch out of the merge", async () => {
    setupGallery({ ids: [1, 2, 3], loaded: [rom(1), rom(2)] });
    const selection = storeGallerySelection();
    const d = deferred<ReturnType<typeof resultPage>>();
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
    // finish the bootstrap with an empty index and no gallery context.
    const galleryRoms = storeGalleryRoms();
    const selection = storeGallerySelection();
    galleryRoms.metadataLoaded = true;
    galleryRoms.byPosition.set(0, rom(1));
    galleryRoms.byPosition.set(1, rom(2));

    const { selectAll, allSelected } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
    expect(selection.ids.sort((a, b) => a - b)).toEqual([1, 2]);
    expect(allSelected.value).toBe(true);
  });

  it("stays loaded-only on opt-out surfaces even before any window lands", async () => {
    const galleryRoms = storeGalleryRoms();
    galleryRoms.metadataLoaded = true;

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
  });

  it("does nothing on an empty filtered result", async () => {
    setupGallery({ ids: [] });
    const selection = storeGallerySelection();

    const { selectAll } = useGallerySelectAll();
    await selectAll();

    expect(getRoms).not.toHaveBeenCalled();
    expect(selection.count).toBe(0);
  });

  it("surfaces a snackbar when the whole-result fetch fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    setupGallery({ ids: [1, 2] });
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
    setupGallery({ ids: [1, 2] });
    const selection = storeGallerySelection();

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");

    selection.selectMany([rom(1)]);
    expect(selectionState.value).toBe("some");

    selection.selectMany([rom(2)]);
    expect(selectionState.value).toBe("all");
  });

  it("reports off over an empty result despite out-of-filter picks", () => {
    setupGallery({ ids: [] });
    const selection = storeGallerySelection();
    selection.selectMany([rom(9)]);

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");
  });

  it("reports off when the selection holds only out-of-filter roms", () => {
    setupGallery({ ids: [1, 2] });
    const selection = storeGallerySelection();
    selection.selectMany([rom(9)]);

    const { selectionState } = useGallerySelectAll();
    expect(selectionState.value).toBe("off");
  });
});
