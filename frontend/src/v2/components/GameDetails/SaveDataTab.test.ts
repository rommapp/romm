import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserSaveSchema, UserStateSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import { saveFixture, stateFixture } from "@/utils/assets.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import { toUserSave, toUserState } from "@/v2/utils/saveStates.fixtures";
import SaveDataTab from "./SaveDataTab.vue";

vi.mock("vue-i18n");
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
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));
const { uploadSaves } = vi.hoisted(() => ({ uploadSaves: vi.fn() }));
vi.mock("@/services/api/save", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/api/save")>();
  return { ...actual, default: { ...actual.default, uploadSaves } };
});

const UploadAssetDialog = {
  props: { cores: { type: Array, default: () => [] } },
  template: `<div class="upload-dialog" />`,
};

function state(id: number, emulator: string): UserStateSchema {
  return toUserState(stateFixture({ id, emulator }), "player");
}

function save(id: number, emulator: string): UserSaveSchema {
  return toUserSave(saveFixture({ id, emulator }), "player");
}

function mountTab(states: UserStateSchema[], saves: UserSaveSchema[] = []) {
  return mount(SaveDataTab, {
    props: {
      rom: detailedRomFixture({
        id: 1,
        platform_slug: "ps2",
        all_user_saves: saves,
        all_user_states: states,
      }),
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
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
  });

  it("offers an emulator configured in another case once", () => {
    const wrapper = mountTab([state(1, "play"), state(2, "Play")]);

    expect(wrapper.findComponent(UploadAssetDialog).props("cores")).toEqual([
      "play",
    ]);
  });

  it("offers the cores existing saves carry", () => {
    const wrapper = mountTab([state(1, "play")], [save(2, "pcsx2")]);

    expect(wrapper.findComponent(UploadAssetDialog).props("cores")).toEqual([
      "pcsx2",
      "play",
    ]);
  });

  it("files an uploaded save under the picked core", async () => {
    uploadSaves.mockResolvedValue([]);
    const wrapper = mountTab([]);
    const file = new File(["x"], "a.srm");

    wrapper.findComponent(UploadAssetDialog).vm.$emit("submit", {
      type: "save",
      files: [file],
      slot: null,
      emulator: "mgba",
    });

    await vi.waitFor(() =>
      expect(uploadSaves).toHaveBeenCalledWith(
        expect.objectContaining({ emulator: "mgba", slot: undefined }),
      ),
    );
  });
});
