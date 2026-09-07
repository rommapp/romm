import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import storeCollections, { type Collection } from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import SelectionBar from "./SelectionBar.vue";

const {
  addRomsToCollection,
  createCollection,
  getCollections,
  removeRomsFromCollection,
  snackbarError,
  snackbarSuccess,
} = vi.hoisted(() => ({
  addRomsToCollection: vi.fn(),
  createCollection: vi.fn(),
  getCollections: vi.fn(),
  removeRomsFromCollection: vi.fn(),
  snackbarError: vi.fn(),
  snackbarSuccess: vi.fn(),
}));

// `t` echoes the key plus its params so a test can assert *which* message was
// shown -- the whole point of the add/remove polarity cases.
vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}::${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("@/services/api/collection", () => ({
  default: {
    addRomsToCollection,
    createCollection,
    getCollections,
    removeRomsFromCollection,
  },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: snackbarSuccess,
    error: snackbarError,
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useCan", () => ({
  useCan: () => ({ value: true }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ xs: ref(false) }),
}));

function rom(id: number): SimpleRom {
  return { id, name: `Game ${id}`, platform_id: 1 } as SimpleRom;
}

function favorites(romIds: number[]): Collection {
  return {
    id: 7,
    name: "Favorites",
    is_favorite: true,
    rom_ids: romIds,
    rom_count: romIds.length,
  } as Collection;
}

function select(...roms: SimpleRom[]) {
  const selection = storeGallerySelection();
  roms.forEach((r, i) => selection.toggle(r, i));
}

function mountBar() {
  return mount(SelectionBar, {
    global: {
      stubs: {
        RToolbar: {
          template:
            "<div><slot name='prepend' /><slot /><slot name='append' /></div>",
        },
        RTooltip: {
          template: "<div><slot name='activator' :props='{}' /></div>",
        },
        RBtn: {
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RMenu: true,
        RMenuItem: true,
        RIcon: true,
        RDivider: true,
      },
    },
  });
}

// The heart's label flips with `allFavorited`, so accept either.
function heart(wrapper: VueWrapper) {
  const add = wrapper.find('[aria-label="gallery.selection-favorite"]');
  return add.exists()
    ? add
    : wrapper.get('[aria-label="gallery.selection-unfavorite"]');
}

async function clickHeart(wrapper: VueWrapper) {
  await heart(wrapper).trigger("click");
  await flushPromises();
}

describe("SelectionBar bulk favorite", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("creates the favourites collection when the instance has none", async () => {
    getCollections.mockResolvedValue({ data: [] });
    createCollection.mockResolvedValue(favorites([]));
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(createCollection).toHaveBeenCalledTimes(1);
    expect(addRomsToCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-favorite-success::{"n":2}',
    );
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("reports an add as added, not removed", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([])]);
    collections.setFavoriteCollection(favorites([]));
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(addRomsToCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-favorite-success::{"n":2}',
    );
  });

  it("reports a removal as removed, not added", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1, 2])]);
    collections.setFavoriteCollection(favorites([1, 2]));
    removeRomsFromCollection.mockResolvedValue({ data: favorites([]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(removeRomsFromCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-unfavorite-success::{"n":2}',
    );
  });

  it("adds when only some of the selection is favourited", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1])]);
    collections.setFavoriteCollection(favorites([1]));
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(addRomsToCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(removeRomsFromCollection).not.toHaveBeenCalled();
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-favorite-success::{"n":2}',
    );
  });

  it("drops the roms from the grid when unfavouriting inside the favourites collection", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1, 2])]);
    collections.setFavoriteCollection(favorites([1, 2]));
    removeRomsFromCollection.mockResolvedValue({ data: favorites([]) });
    const gallery = storeGalleryRoms();
    gallery.setCurrentCollection(favorites([1, 2]));
    const galleryRemove = vi.spyOn(gallery, "remove").mockImplementation(() => {
      /* the real one refetches the gallery */
    });
    const roms = storeRoms();
    const romsRemove = vi.spyOn(roms, "remove");
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(galleryRemove).toHaveBeenCalledTimes(1);
    expect(galleryRemove.mock.calls[0][0].map((r) => r.id)).toEqual([1, 2]);
    expect(romsRemove).toHaveBeenCalledTimes(1);
    expect(storeGallerySelection().count).toBe(0);
  });

  it("keeps the roms on screen when unfavouriting from a platform gallery", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1, 2])]);
    collections.setFavoriteCollection(favorites([1, 2]));
    removeRomsFromCollection.mockResolvedValue({ data: favorites([]) });
    const gallery = storeGalleryRoms();
    const galleryRemove = vi.spyOn(gallery, "remove");
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(removeRomsFromCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(galleryRemove).not.toHaveBeenCalled();
    expect(storeGallerySelection().count).toBe(2);
  });

  it("surfaces an error when the collection cannot be created", async () => {
    getCollections.mockResolvedValue({ data: [] });
    createCollection.mockRejectedValue(new Error("Forbidden"));
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(addRomsToCollection).not.toHaveBeenCalled();
    expect(snackbarError).toHaveBeenCalledWith(
      "gallery.selection-favorite-fail",
    );
    expect(snackbarSuccess).not.toHaveBeenCalled();
  });

  it("does nothing without a selection", async () => {
    getCollections.mockResolvedValue({ data: [] });

    await clickHeart(mountBar());

    expect(createCollection).not.toHaveBeenCalled();
    expect(addRomsToCollection).not.toHaveBeenCalled();
    expect(snackbarSuccess).not.toHaveBeenCalled();
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("ignores a second click while the first is still in flight", async () => {
    getCollections.mockResolvedValue({ data: [] });
    createCollection.mockResolvedValue(favorites([]));
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));
    const wrapper = mountBar();

    await heart(wrapper).trigger("click");
    await heart(wrapper).trigger("click");
    await flushPromises();

    expect(createCollection).toHaveBeenCalledTimes(1);
    expect(addRomsToCollection).toHaveBeenCalledTimes(1);
  });
});
