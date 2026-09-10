import { shallowMount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRomSchema, UserStateSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";
import SaveDataTab from "./SaveDataTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ path: "/rom/1", query: { subtab: "states" } }),
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => vi.fn().mockResolvedValue(false),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom: vi.fn(), syncCachedRom: vi.fn() }),
}));

const MY_ID = 7;

function makeState(id: number, userId: number): UserStateSchema {
  return {
    id,
    rom_id: 1,
    user_id: userId,
    file_name: `state_${id}.state`,
    file_size_bytes: 524288,
    download_path: `/api/states/${id}/content`,
    missing_from_fs: false,
    created_at: "2026-05-13T22:08:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "snes9x",
    screenshot: null,
    username: userId === MY_ID ? "me" : "someone-else",
  } as UserStateSchema;
}

function mountTab() {
  return shallowMount(SaveDataTab, {
    // The "Mine" list lives inside an overlay dropzone, and a default stub
    // renders no slot, so that half of the tab would be invisible here.
    global: { stubs: { RDropzone: { template: "<div><slot /></div>" } } },
    props: {
      rom: {
        id: 1,
        all_user_saves: [],
        all_user_states: [makeState(1, MY_ID), makeState(2, 99)],
      } as unknown as DetailedRomSchema,
    },
  });
}

beforeEach(() => {
  setActivePinia(createPinia());
  storeAuth().user = { id: MY_ID } as User;
});

// Issue #4320: states used to render as 150px AssetStrip tiles that dropped the
// emulator chip and the exact timestamp and truncated the filename unrecoverably.
describe("SaveDataTab states subtab", () => {
  it("renders states through AssetList, like saves", () => {
    const lists = mountTab()
      .findAllComponents({ name: "AssetList" })
      .filter((l) => l.props("type") === "state");

    expect(lists).toHaveLength(2);
    for (const list of lists) {
      expect(list.props("selectable")).toBe(false);
      // The tab owns its own scroll, so the list must not add a second one.
      expect(list.props("scrollable")).toBe(false);
    }
  });

  it("no longer mounts an AssetStrip", () => {
    expect(mountTab().findAllComponents({ name: "AssetStrip" })).toHaveLength(
      0,
    );
  });

  it("credits the author on community states only", () => {
    const lists = mountTab()
      .findAllComponents({ name: "AssetList" })
      .filter((l) => l.props("type") === "state");

    expect(lists.map((l) => l.props("showOwner"))).toEqual([false, true]);
  });
});
