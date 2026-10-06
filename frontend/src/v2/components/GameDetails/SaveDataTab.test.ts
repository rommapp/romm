import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ChannelSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import storeAuth from "@/stores/auth";
import { saveFixture } from "@/utils/assets.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import { userFixture } from "@/utils/user.fixtures";
import ChannelsPanel from "@/v2/components/GameDetails/SaveChannels/ChannelsPanel.vue";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { channelFixture } from "@/v2/utils/snapshots.fixtures";
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

function mountTab(
  states: UserStateSchema[],
  {
    saves = [],
    channels = [],
  }: { saves?: UserSaveSchema[]; channels?: ChannelSchema[] } = {},
) {
  return mount(SaveDataTab, {
    props: {
      rom: detailedRomFixture({
        id: 1,
        platform_slug: "ps2",
        all_user_saves: saves,
        all_user_states: states,
        user_channels: channels,
      }),
    },
    global: {
      stubs: {
        UploadAssetDialog,
        SubtabNav: true,
        AssetStrip: true,
        AssetList: true,
        ChannelsPanel: true,
        RDropzone: { template: "<div><slot /></div>" },
        RBtn: true,
      },
    },
  });
}

describe("SaveDataTab channel segregation", () => {
  const own = channelFixture();
  const shared = channelFixture({
    id: "0192f1c4-0000-7000-8000-000000000009",
    is_own: false,
    owner_username: "kai",
  });
  const userSave = (over: Partial<UserSaveSchema>): UserSaveSchema => ({
    ...saveFixture(over),
    username: over.user_id === 2 ? "kai" : "nendo",
  });
  const backup = userSave({ id: 1 });
  const legacy = userSave({ id: 2, channel_id: own.id, slot: "autosave" });
  const snapshotSave = userSave({ id: 3, channel_id: own.id });
  const otherBackup = userSave({ id: 4, user_id: 2 });
  const otherLinked = userSave({ id: 5, user_id: 2, channel_id: shared.id });
  const backupState = { ...state(6, "snes9x"), channel_id: null };
  const channelState = { ...state(7, "snes9x"), channel_id: own.id };

  beforeEach(() => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
  });

  function mountSegregated() {
    return mountTab([backupState, channelState], {
      saves: [backup, legacy, snapshotSave, otherBackup, otherLinked],
      channels: [own, shared],
    });
  }

  it("lists only unchanneled saves and states as backups", () => {
    const wrapper = mountSegregated();
    const [mine, community] = wrapper.findAllComponents(AssetList);

    expect(mine?.props("assets")).toEqual([backup]);
    expect(community?.props("assets")).toEqual([otherBackup]);
    expect(wrapper.findComponent(AssetStrip).props("assets")).toEqual([
      backupState,
    ]);
  });

  it("hands own channels every own save and shared channels none", () => {
    const wrapper = mountSegregated();
    const [mine, community] = wrapper.findAllComponents(ChannelsPanel);

    expect(mine?.props("channels")).toEqual([own]);
    expect(mine?.props("saves")).toEqual([backup, legacy, snapshotSave]);
    expect(community?.props("channels")).toEqual([shared]);
    expect(community?.props("saves")).toEqual([]);
  });
});

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
});
