import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive } from "vue";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { makeDetailedRom, makeRom } from "@/utils/rom.fixtures";
import DeleteRomDialog from "./DeleteRomDialog.vue";

const { addExclusion, deleteRoms, push, snackbarError } = vi.hoisted(() => ({
  addExclusion: vi.fn(),
  deleteRoms: vi.fn(),
  push: vi.fn(),
  snackbarError: vi.fn(),
}));
const route = reactive<{ name: string; params: Record<string, string> }>({
  name: "rom",
  params: { rom: "5" },
});

vi.mock("vue-i18n");
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => route,
  useRouter: () => ({ push }),
}));
vi.mock("@/plugins/router", () => ({ ROUTES: { PLATFORM: "platform" } }));
vi.mock("@/services/api/rom", () => ({ default: { deleteRoms } }));
vi.mock("@/services/api/config", () => ({
  default: { addExclusion },
}));
vi.mock("@/stores/config", () => ({
  default: () => ({ addExclusion: vi.fn() }),
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ removeCachedRoms: vi.fn() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="append" /><slot name="footer" /></div>`,
};
const RBtn = {
  emits: ["click"],
  template: `<button type="button" @click="$emit('click')"><slot /></button>`,
};
const RCheckbox = {
  emits: ["update:modelValue"],
  template: `<input type="checkbox" @change="$emit('update:modelValue', true)" />`,
};
// happy-dom lays nothing out, so a windowed list would render no rows.
const WholeList = defineComponent({
  props: { items: { type: Array, default: () => [] } },
  template: `<div><div v-for="(item, index) in items" :key="index"><slot :item="item" :index="index" /></div></div>`,
});
const stubs = {
  RDialog,
  RBtn,
  RCheckbox,
  RIcon: true,
  RVirtualScroller: WholeList,
};

async function deleteShownGame() {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(DeleteRomDialog, {
    global: {
      provide: { emitter },
      stubs,
    },
  });
  emitter.emit("showDeleteRomDialog", [
    makeRom({ id: 5, platform_id: 1 }),
    makeRom({ id: 6, platform_id: 1 }),
  ]);
  await flushPromises();
  // The footer's confirm button renders last.
  await wrapper.findAll("button").at(-1)?.trigger("click");
  await flushPromises();
  expect(deleteRoms).toHaveBeenCalledOnce();
}

describe("DeleteRomDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    route.name = "rom";
    route.params = { rom: "5" };
    deleteRoms.mockResolvedValue({
      data: { failed_ids: [], successful_items: 2 },
    });
    const roms = storeRoms();
    roms.cacheDetailedRom(makeDetailedRom({ id: 5 }));
    roms.cacheDetailedRom(makeDetailedRom({ id: 6 }));
  });

  it("forgets the deleted games once the page has left them", async () => {
    push.mockImplementation(async () => {
      route.name = "platform";
      route.params = { platform: "1" };
    });

    await deleteShownGame();

    expect(storeRoms().getDetailedRom(5)).toBeNull();
    expect(storeRoms().getDetailedRom(6)).toBeNull();
  });

  it("keeps the shown game's record when the redirect fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    push.mockRejectedValue(new Error("guard failed"));

    await deleteShownGame();

    expect(snackbarError).not.toHaveBeenCalled();
    expect(storeRoms().getDetailedRom(5)).not.toBeNull();
    expect(storeRoms().getDetailedRom(6)).toBeNull();
  });
});

describe("DeleteRomDialog with a large selection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    deleteRoms.mockResolvedValue({
      data: { failed_ids: [], successful_items: 120 },
    });
  });

  async function openWith(count: number) {
    const emitter: Emitter<Events> = mitt<Events>();
    const wrapper = mount(DeleteRomDialog, {
      global: {
        provide: { emitter },
        stubs,
      },
    });
    emitter.emit(
      "showDeleteRomDialog",
      Array.from({ length: count }, (_, i) =>
        makeRom({ id: i + 1, platform_id: 1 }),
      ),
    );
    await flushPromises();
    return wrapper;
  }

  it("hands every selected game to the virtual scroller", async () => {
    const wrapper = await openWith(120);

    expect(wrapper.findComponent(WholeList).props("items")).toHaveLength(120);
  });

  it("waits for the exclusions and reports the ones that failed", async () => {
    addExclusion
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("config not writable"));
    const wrapper = await openWith(2);

    await wrapper.find('input[type="checkbox"]').trigger("change");
    await wrapper.findAll("button").at(-1)?.trigger("click");
    await flushPromises();

    expect(addExclusion).toHaveBeenCalledTimes(2);
    expect(snackbarError).toHaveBeenCalledWith(
      "rom.exclude-failed",
      expect.anything(),
    );
  });

  it("deletes every selected game", async () => {
    const wrapper = await openWith(120);

    await wrapper.findAll("button").at(-1)?.trigger("click");
    await flushPromises();

    const sent = deleteRoms.mock.calls[0][0] as { roms: { id: number }[] };
    expect(sent.roms).toHaveLength(120);
  });
});
