import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import storeAuth from "@/stores/auth";
import storeCollections, { type Collection } from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import { collectionFixture } from "@/utils/collection.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import SelectionBar from "./SelectionBar.vue";
import { selectionBarOutline } from "./selectionBarOutline";

const {
  addRomsToCollection,
  createCollection,
  getCollections,
  removeRomsFromCollection,
  selectAll,
  snackbarError,
  snackbarSuccess,
  updateUserRomProps,
} = vi.hoisted(() => ({
  addRomsToCollection: vi.fn(),
  createCollection: vi.fn(),
  getCollections: vi.fn(),
  removeRomsFromCollection: vi.fn(),
  selectAll: vi.fn(),
  snackbarError: vi.fn(),
  snackbarSuccess: vi.fn(),
  updateUserRomProps: vi.fn(),
}));

// The whole-result behavior is covered by the composable's own tests;
// here we only assert the bar's wiring to it.
vi.mock("@/v2/composables/useGallerySelectAll", () => ({
  useGallerySelectAll: () => ({
    selectingAll: ref(false),
    allSelected: ref(false),
    selectAll,
  }),
}));

// `t` echoes the key plus its params so a test can assert *which* message was
// shown -- the whole point of the add/remove polarity cases.
vi.mock("vue-i18n");

// Importing the real router also pulls in its lazy auth views, which can still
// be loading when the test environment tears down.
vi.mock("@/plugins/router", () => ({
  default: {},
  ROUTES: {},
  isAuthExemptRoute: () => false,
}));

vi.mock("@/services/api/collection", () => ({
  default: {
    addRomsToCollection,
    createCollection,
    getCollections,
    removeRomsFromCollection,
  },
}));

vi.mock("@/services/api/rom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/api/rom")>();
  return {
    default: { ...actual.default, updateUserRomProps },
  };
});

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
  return collectionFixture({
    id: 7,
    is_favorite: true,
    rom_ids: romIds,
    rom_count: romIds.length,
  });
}

function select(...roms: SimpleRom[]) {
  const selection = storeGallerySelection();
  roms.forEach((r, i) => selection.toggle(r, i));
}

function mountBar(
  props: { hideDownload?: boolean } = {},
  extraStubs: Record<string, unknown> = {},
) {
  return mount(SelectionBar, {
    props,
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
        ...extraStubs,
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
    storeAuth().setCurrentUser(userFixture());
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
      'gallery.selection-favorite-success:{"n":2}',
    );
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("reports an add as added, not removed", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([])]);
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(addRomsToCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-favorite-success:{"n":2}',
    );
  });

  it("reports a removal as removed, not added", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1, 2])]);
    removeRomsFromCollection.mockResolvedValue({ data: favorites([]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(removeRomsFromCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-unfavorite-success:{"n":2}',
    );
  });

  it("adds when only some of the selection is favourited", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1])]);
    addRomsToCollection.mockResolvedValue({ data: favorites([1, 2]) });
    select(rom(1), rom(2));

    await clickHeart(mountBar());

    expect(addRomsToCollection).toHaveBeenCalledWith(7, [1, 2]);
    expect(removeRomsFromCollection).not.toHaveBeenCalled();
    expect(snackbarSuccess).toHaveBeenCalledWith(
      'gallery.selection-favorite-success:{"n":2}',
    );
  });

  it("drops the roms from the grid when unfavouriting inside the favourites collection", async () => {
    const collections = storeCollections();
    collections.setCollections([favorites([1, 2])]);
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

describe("SelectionBar download", () => {
  it("offers the download action by default", () => {
    select(rom(1));

    expect(
      mountBar().find('[aria-label="gallery.selection-download"]').exists(),
    ).toBe(true);
  });

  // Hosts whose rows have no file on disk (the Missing games tab) opt out,
  // so the bar never offers a transfer that can only fail.
  it("drops the download action when the host hides it", () => {
    select(rom(1));

    expect(
      mountBar({ hideDownload: true })
        .find('[aria-label="gallery.selection-download"]')
        .exists(),
    ).toBe(false);
  });
});

describe("SelectionBar select all", () => {
  it("triggers the whole-result select-all", async () => {
    select(rom(1));
    const wrapper = mountBar();

    await wrapper
      .get('[aria-label="gallery.selection-select-all"]')
      .trigger("click");

    expect(selectAll).toHaveBeenCalledTimes(1);
  });

  it("labels the button with the filtered-result total when known", () => {
    storeGalleryRoms().total = 42;
    select(rom(1));
    const wrapper = mountBar();

    expect(
      wrapper
        .find("[aria-label='gallery.selection-select-all-count:{\"n\":42}']")
        .exists(),
    ).toBe(true);
  });
});

describe("SelectionBar bulk status", () => {
  it("ignores a status choice while the previous batch is running", async () => {
    let finish: () => void = () => {};
    updateUserRomProps.mockImplementation(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    select(rom(1));
    const wrapper = mountBar(
      {},
      {
        RMenu: { template: "<div><slot /></div>" },
        RMenuItem: {
          props: { disabled: Boolean },
          emits: ["click"],
          template:
            "<button class='status-item' :disabled='disabled' @click=\"$emit('click')\"><slot /></button>",
        },
      },
    );
    const [first, second] = wrapper.findAll(".status-item");

    await first.trigger("click");
    await second.trigger("click");
    expect(updateUserRomProps).toHaveBeenCalledTimes(1);
    expect(second.attributes("disabled")).toBeDefined();

    finish();
    await flushPromises();
    await second.trigger("click");
    expect(updateUserRomProps).toHaveBeenCalledTimes(2);
  });
});

describe("SelectionBar outline", () => {
  beforeEach(() => {
    storeAuth().setCurrentUser(userFixture());
  });

  it("draws the outline from the bar's and notch's measured sizes", async () => {
    const observer = stubResizeObserver();
    const wrapper = mountBar();
    await flushPromises();
    expect(wrapper.find(".selection-bar__outline").exists()).toBe(false);

    // Padding makes each border box bigger than its content box; the outline
    // has to trace the border box.
    observer.resize(wrapper.get(".selection-bar").element, 580, 40, {
      width: 600,
      height: 48,
    });
    observer.resize(wrapper.get(".selection-bar__notch").element, 48, 32, {
      width: 64,
      height: 40,
    });
    await nextTick();

    const expected = selectionBarOutline({ w: 600, h: 48 }, { w: 64, h: 40 });
    const svg = wrapper.get(".selection-bar__outline");
    expect(svg.attributes("width")).toBe(String(expected?.width));
    expect(svg.get("path").attributes("d")).toBe(expected?.d);
  });
});
