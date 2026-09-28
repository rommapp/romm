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
