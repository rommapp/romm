import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reactive } from "vue";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { makeDetailedRom, makeRom } from "@/utils/rom.fixtures";
import DeleteRomDialog from "./DeleteRomDialog.vue";

const { deleteRoms, push, snackbarError } = vi.hoisted(() => ({
  deleteRoms: vi.fn(),
  push: vi.fn(),
  snackbarError: vi.fn(),
}));
const route = reactive<{ name: string; params: Record<string, string> }>({
  name: "rom",
  params: { rom: "5" },
});

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => route,
  useRouter: () => ({ push }),
}));
vi.mock("@/plugins/router", () => ({ ROUTES: { PLATFORM: "platform" } }));
vi.mock("@/services/api/rom", () => ({ default: { deleteRoms } }));
vi.mock("@/services/api/config", () => ({
  default: { addExclusion: vi.fn() },
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
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};
const RBtn = {
  emits: ["click"],
  template: `<button type="button" @click="$emit('click')"><slot /></button>`,
};

async function deleteShownGame() {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(DeleteRomDialog, {
    global: {
      provide: { emitter },
      stubs: { RDialog, RBtn, RCheckbox: true, RIcon: true },
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
    setActivePinia(createPinia());
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
    setActivePinia(createPinia());
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
        stubs: { RDialog, RBtn, RCheckbox: true, RIcon: true },
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

  it("renders rows a page at a time", async () => {
    const wrapper = await openWith(120);
    expect(wrapper.findAll(".r-v2-del-rom__row")).toHaveLength(50);

    await wrapper.find(".r-v2-del-rom__more button").trigger("click");
    expect(wrapper.findAll(".r-v2-del-rom__row")).toHaveLength(100);

    await wrapper.find(".r-v2-del-rom__more button").trigger("click");
    expect(wrapper.findAll(".r-v2-del-rom__row")).toHaveLength(120);
    expect(wrapper.find(".r-v2-del-rom__more").exists()).toBe(false);
  });

  it("still deletes the rows that were never shown", async () => {
    const wrapper = await openWith(120);

    await wrapper.findAll("button").at(-1)?.trigger("click");
    await flushPromises();

    const sent = deleteRoms.mock.calls[0][0] as { roms: { id: number }[] };
    expect(sent.roms).toHaveLength(120);
  });
});
