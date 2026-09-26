import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRomSchema, UserStateSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";
import SaveDataTab from "./SaveDataTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ query: {}, path: "/rom/1", params: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({ useConfirm: () => vi.fn() }));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom: vi.fn() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const UploadAssetDialog = {
  props: { cores: { type: Array, default: () => [] } },
  template: `<div class="upload-dialog" />`,
};

function state(id: number, emulator: string): UserStateSchema {
  return {
    id,
    user_id: 1,
    file_name: `state_${id}.state`,
    updated_at: "2026-09-16T10:00:00Z",
    emulator,
  } as UserStateSchema;
}

function mountTab(states: UserStateSchema[]) {
  return mount(SaveDataTab, {
    props: {
      rom: {
        id: 1,
        platform_slug: "ps2",
        all_user_saves: [],
        all_user_states: states,
      } as unknown as DetailedRomSchema,
    },
    global: {
      stubs: {
        UploadAssetDialog,
        SubtabNav: true,
        AssetStrip: true,
        AssetList: true,
        RDropzone: true,
        RBtn: true,
      },
    },
  });
}

describe("SaveDataTab upload cores", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    storeAuth().setCurrentUser({ id: 1 } as User);
  });

  it("offers an emulator configured in another case once", () => {
    const wrapper = mountTab([state(1, "play"), state(2, "Play")]);

    expect(wrapper.findComponent(UploadAssetDialog).props("cores")).toEqual([
      "play",
    ]);
  });
});
