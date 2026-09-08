import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import storeAuth from "@/stores/auth";
import storeCollections, { type Collection } from "@/stores/collections";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import ManageCollectionsDialog from "./ManageCollectionsDialog.vue";

const { addRomsToCollection, removeRomsFromCollection, snackbarError } =
  vi.hoisted(() => ({
    addRomsToCollection: vi.fn(),
    removeRomsFromCollection: vi.fn(),
    snackbarError: vi.fn(),
  }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api/collection", () => ({
  default: {
    addRomsToCollection,
    removeRomsFromCollection,
    createCollection: vi.fn(),
  },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: snackbarError,
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ mdAndUp: ref(true) }),
}));

vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({ toWebp: (url: string) => url }),
}));

const USER_ID = 3;

function rom(id: number): SimpleRom {
  return { id, name: `Game ${id}`, platform_id: 1 } as SimpleRom;
}

function collection(romIds: number[]): Collection {
  return {
    id: 12,
    name: "Shooters",
    user_id: USER_ID,
    rom_ids: romIds,
    rom_count: romIds.length,
  } as Collection;
}

/** Mount the dialog, open it over `roms`, and click the one collection row. */
async function toggleRow(roms: SimpleRom[]) {
  const emitter = mitt<Events>();
  const wrapper = mountDialog(emitter);
  await open(wrapper, emitter, roms);
  await wrapper.get("[data-test-row]").trigger("click");
  await flushPromises();
  return { wrapper, emitter };
}

async function open(
  wrapper: VueWrapper,
  emitter: Emitter<Events>,
  roms: SimpleRom[],
) {
  emitter.emit("showManageCollectionsDialog", roms);
  await flushPromises();
}

/** The tri-state the row is currently painting. */
function rowState(wrapper: VueWrapper) {
  return wrapper.get("[data-test-row]").attributes("data-state");
}

function mountDialog(emitter: Emitter<Events>): VueWrapper {
  return mount(ManageCollectionsDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: { template: "<div><slot name='content' /></div>" },
        RDivider: true,
        GameCard: true,
        NewCollectionRow: true,
        CollectionPickerRow: {
          props: ["state"],
          emits: ["toggle"],
          template:
            '<button data-test-row :data-state="state" @click="$emit(\'toggle\')"></button>',
        },
      },
    },
  });
}

describe("ManageCollectionsDialog gallery reconcile", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    storeAuth().setCurrentUser({ id: USER_ID } as User);
  });

  it("drops the roms from the gallery when removing them from the collection on screen", async () => {
    const collections = storeCollections();
    collections.setCollections([collection([1, 2])]);
    removeRomsFromCollection.mockResolvedValue({ data: collection([]) });
    const gallery = storeGalleryRoms();
    gallery.setCurrentCollection(collection([1, 2]));
    const galleryRemove = vi.spyOn(gallery, "remove").mockImplementation(() => {
      /* the real one refetches the gallery */
    });
    const romsRemove = vi.spyOn(storeRoms(), "remove");
    const selection = storeGallerySelection();
    [rom(1), rom(2)].forEach((r, i) => selection.toggle(r, i));

    await toggleRow([rom(1), rom(2)]);

    expect(removeRomsFromCollection).toHaveBeenCalledWith(12, [1, 2]);
    expect(galleryRemove).toHaveBeenCalledTimes(1);
    expect(galleryRemove.mock.calls[0][0].map((r) => r.id)).toEqual([1, 2]);
    expect(romsRemove).toHaveBeenCalledTimes(1);
    expect(selection.count).toBe(0);
  });

  it("keeps the roms on screen when removing them from a collection it isn't showing", async () => {
    const collections = storeCollections();
    collections.setCollections([collection([1, 2])]);
    removeRomsFromCollection.mockResolvedValue({ data: collection([]) });
    const gallery = storeGalleryRoms();
    gallery.setCurrentCollection({ ...collection([]), id: 99 } as Collection);
    const galleryRemove = vi.spyOn(gallery, "remove");

    await toggleRow([rom(1), rom(2)]);

    expect(removeRomsFromCollection).toHaveBeenCalledWith(12, [1, 2]);
    expect(galleryRemove).not.toHaveBeenCalled();
  });

  it("keeps the roms on screen when adding them to the collection on screen", async () => {
    const collections = storeCollections();
    collections.setCollections([collection([])]);
    addRomsToCollection.mockResolvedValue({ data: collection([1, 2]) });
    const gallery = storeGalleryRoms();
    gallery.setCurrentCollection(collection([]));
    const galleryRemove = vi.spyOn(gallery, "remove");

    await toggleRow([rom(1), rom(2)]);

    expect(addRomsToCollection).toHaveBeenCalledWith(12, [1, 2]);
    expect(galleryRemove).not.toHaveBeenCalled();
  });

  it("leaves the gallery alone when the removal fails", async () => {
    const collections = storeCollections();
    collections.setCollections([collection([1, 2])]);
    removeRomsFromCollection.mockRejectedValue(new Error("Forbidden"));
    const gallery = storeGalleryRoms();
    gallery.setCurrentCollection(collection([1, 2]));
    const galleryRemove = vi.spyOn(gallery, "remove");
    const selection = storeGallerySelection();
    [rom(1), rom(2)].forEach((r, i) => selection.toggle(r, i));

    const { wrapper } = await toggleRow([rom(1), rom(2)]);

    expect(galleryRemove).not.toHaveBeenCalled();
    expect(selection.count).toBe(2);
    expect(snackbarError).toHaveBeenCalled();
    // Nothing was written, so the row goes back to real membership.
    expect(rowState(wrapper)).toBe("all");
  });

  it("does not pin the row when a failure lands after the dialog reopens", async () => {
    const collections = storeCollections();
    collections.setCollections([collection([1, 2])]);
    let reject: (reason: Error) => void = () => {};
    removeRomsFromCollection.mockReturnValue(
      new Promise((_resolve, r) => {
        reject = r;
      }),
    );
    const emitter = mitt<Events>();
    const wrapper = mountDialog(emitter);

    await open(wrapper, emitter, [rom(1), rom(2)]);
    await wrapper.get("[data-test-row]").trigger("click");
    // Reopened over a game the collection doesn't hold, while the removal
    // above is still in flight.
    await open(wrapper, emitter, [rom(3)]);
    reject(new Error("Forbidden"));
    await flushPromises();

    expect(rowState(wrapper)).toBe("off");
  });
});
