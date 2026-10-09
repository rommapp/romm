import { flushPromises, shallowMount } from "@vue/test-utils";
import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChannelSchema, SaveSchema } from "@/__generated__";
import snapshotApi from "@/services/api/snapshot";
import { saveFixture } from "@/utils/assets.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import ChannelFan from "@/v2/components/GameDetails/SaveChannels/ChannelFan.vue";
import ChannelLabelDialog from "@/v2/components/GameDetails/SaveChannels/ChannelLabelDialog.vue";
import ChannelTile from "@/v2/components/GameDetails/SaveChannels/ChannelTile.vue";
import DeleteChannelDialog from "@/v2/components/GameDetails/SaveChannels/DeleteChannelDialog.vue";
import SnapshotViewer from "@/v2/components/GameDetails/SaveChannels/SnapshotViewer.vue";
import { channelFixture, snapshotFixture } from "@/v2/utils/snapshots.fixtures";
import ChannelsPanel from "./ChannelsPanel.vue";

const confirm = vi.fn<() => Promise<boolean>>();
const snackbar = { success: vi.fn(), error: vi.fn(), warning: vi.fn() };
const refetchRom = vi.fn();

vi.mock("vue-i18n");
vi.mock("@/services/api/snapshot", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/services/api/snapshot")>();
  return {
    ...actual,
    default: {
      createChannel: vi.fn(),
      updateChannel: vi.fn(),
      deleteChannel: vi.fn(),
      getDetachedChannels: vi.fn(),
      attachChannel: vi.fn(),
      getChannelHistory: vi.fn(),
      pushSnapshot: vi.fn(),
      setSnapshotPinned: vi.fn(),
    },
  };
});
vi.mock("@/v2/composables/useConfirm", () => ({ useConfirm: () => confirm }));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => snackbar,
}));
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom }),
}));

const api = vi.mocked(snapshotApi);

function conflict(data: object): AxiosError {
  return new AxiosError("Conflict", "ERR_BAD_REQUEST", undefined, undefined, {
    data,
    status: 409,
    statusText: "Conflict",
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

function mountPanel(
  channels: ChannelSchema[],
  saves: SaveSchema[] = [],
  heldSaveIds: number[] = [],
) {
  return shallowMount(ChannelsPanel, {
    props: {
      rom: detailedRomFixture({ id: 1, snapshot_save_ids: heldSaveIds }),
      channels,
      saves,
      own: true,
    },
  });
}

/** Expands `channel`'s tile and opens its current snapshot in the viewer. */
async function openCurrent(
  wrapper: ReturnType<typeof mountPanel>,
  channel: ChannelSchema,
) {
  wrapper.findComponent(ChannelTile).vm.$emit("open");
  await flushPromises();
  wrapper.findComponent(ChannelFan).vm.$emit("openSnapshot", channel.current);
  await flushPromises();
}

describe("ChannelsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getChannelHistory.mockResolvedValue({ data: [] } as never);
    api.getDetachedChannels.mockResolvedValue({ data: [] } as never);
  });

  it("restores a snapshot as the channel's new current", async () => {
    const older = snapshotFixture({ id: 40 });
    const channel = channelFixture();
    api.pushSnapshot.mockResolvedValue({} as never);
    const wrapper = mountPanel([channel]);

    await openCurrent(wrapper, channel);
    wrapper.findComponent(ChannelFan).vm.$emit("openSnapshot", older);
    await flushPromises();
    wrapper.findComponent(SnapshotViewer).vm.$emit("restore");
    await flushPromises();

    expect(api.pushSnapshot).toHaveBeenCalledWith({
      manifest: expect.objectContaining({
        channel_id: channel.id,
        expected_current_id: channel.current_snapshot_id,
        parent_snapshot_id: 40,
      }),
    });
    expect(snackbar.success).toHaveBeenCalledWith(
      "channels.restored",
      expect.anything(),
    );
    expect(refetchRom).toHaveBeenCalledWith(1);
  });

  it("refreshes without retrying when another device pushed first", async () => {
    const channel = channelFixture();
    api.pushSnapshot.mockRejectedValue(conflict({ current_snapshot_id: 99 }));
    const wrapper = mountPanel([channel]);

    await openCurrent(wrapper, channel);
    wrapper.findComponent(SnapshotViewer).vm.$emit("restore");
    await flushPromises();

    expect(api.pushSnapshot).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();
    expect(snackbar.warning).toHaveBeenCalledWith(
      "channels.stale",
      expect.anything(),
    );
    expect(snackbar.success).not.toHaveBeenCalled();
    expect(refetchRom).toHaveBeenCalled();
  });

  it("repushes with approval once a hardcore downgrade is confirmed", async () => {
    const channel = channelFixture({ is_hardcore: true });
    api.pushSnapshot
      .mockRejectedValueOnce(conflict({ hardcore_downgrade: true }))
      .mockResolvedValueOnce({} as never);
    confirm.mockResolvedValue(true);
    const wrapper = mountPanel([channel]);

    await openCurrent(wrapper, channel);
    wrapper.findComponent(SnapshotViewer).vm.$emit("restore");
    await flushPromises();

    expect(api.pushSnapshot).toHaveBeenCalledTimes(2);
    expect(api.pushSnapshot).toHaveBeenLastCalledWith({
      manifest: expect.objectContaining({ approve_hardcore_downgrade: true }),
    });
    expect(snackbar.success).toHaveBeenCalled();
  });

  it("keeps the hardcore save when the downgrade is declined", async () => {
    const channel = channelFixture({ is_hardcore: true });
    api.pushSnapshot.mockRejectedValue(conflict({ hardcore_downgrade: true }));
    confirm.mockResolvedValue(false);
    const wrapper = mountPanel([channel]);

    await openCurrent(wrapper, channel);
    wrapper.findComponent(SnapshotViewer).vm.$emit("restore");
    await flushPromises();

    expect(api.pushSnapshot).toHaveBeenCalledTimes(1);
    expect(snackbar.success).not.toHaveBeenCalled();
    expect(snackbar.error).not.toHaveBeenCalled();
  });

  it("offers only backups as a new channel's starting save", async () => {
    const channel = channelFixture();
    const backup = saveFixture({ id: 5, file_name: "backup.srm" });
    const linked = saveFixture({
      id: 6,
      channel_id: channel.id,
      slot: "autosave",
    });
    const wrapper = mountPanel([channel], [backup, linked]);

    await wrapper
      .find(".r-channels__tools")
      .findComponent({ name: "RBtn" })
      .trigger("click");
    await flushPromises();

    expect(
      wrapper.findComponent(ChannelLabelDialog).props("startOptions"),
    ).toEqual([
      { saveId: 5, title: "backup.srm" },
      { saveId: null, title: "channels.start-empty" },
    ]);
  });

  it("creates a channel and copies the chosen backup into it", async () => {
    const channel = channelFixture();
    const created = channelFixture({
      id: "0192f1c4-0000-7000-8000-000000000002",
      label: "Speedrun",
      current: null,
    });
    api.createChannel.mockResolvedValue({ data: created } as never);
    api.pushSnapshot.mockResolvedValue({} as never);
    const wrapper = mountPanel([channel], [saveFixture({ id: 5 })]);

    await wrapper
      .find(".r-channels__tools")
      .findComponent({ name: "RBtn" })
      .trigger("click");
    wrapper
      .findComponent(ChannelLabelDialog)
      .vm.$emit("submit", { label: "Speedrun", startFrom: 5 });
    await flushPromises();

    expect(api.createChannel).toHaveBeenCalledWith({
      romFileId: channel.rom_file_id,
      label: "Speedrun",
    });
    expect(api.pushSnapshot).toHaveBeenCalledWith({
      manifest: expect.objectContaining({
        channel_id: created.id,
        expected_current_id: null,
        save: { copy_of: 5 },
      }),
    });
  });

  it("creates an empty channel without pushing", async () => {
    const channel = channelFixture();
    api.createChannel.mockResolvedValue({
      data: channelFixture({ current: null }),
    } as never);
    const wrapper = mountPanel([channel]);

    await wrapper
      .find(".r-channels__tools")
      .findComponent({ name: "RBtn" })
      .trigger("click");
    wrapper
      .findComponent(ChannelLabelDialog)
      .vm.$emit("submit", { label: "Fresh", startFrom: null });
    await flushPromises();

    expect(api.createChannel).toHaveBeenCalled();
    expect(api.pushSnapshot).not.toHaveBeenCalled();
    expect(snackbar.success).toHaveBeenCalledWith(
      "channels.created",
      expect.anything(),
    );
  });

  /** Opens `channel`'s fan and asks to delete it. */
  async function askToDelete(wrapper: ReturnType<typeof mountPanel>) {
    wrapper.findComponent(ChannelTile).vm.$emit("open");
    await flushPromises();
    wrapper.findComponent(ChannelFan).vm.$emit("delete");
    await flushPromises();
    return wrapper.findComponent(DeleteChannelDialog);
  }

  it("deletes a channel from inside its confirmation", async () => {
    const channel = channelFixture({ label: "Main" });
    const legacy = saveFixture({
      id: 6,
      channel_id: channel.id,
      slot: "autosave",
    });
    api.deleteChannel.mockResolvedValue({} as never);
    const wrapper = mountPanel([channel], [legacy]);

    const dialog = await askToDelete(wrapper);

    expect(dialog.props()).toMatchObject({
      channel,
      body: 'channels.delete-body:{"pinned":0,"legacy":1}',
    });
    expect(api.deleteChannel).not.toHaveBeenCalled();
    await dialog.props("onConfirm")();
    await flushPromises();

    expect(api.deleteChannel).toHaveBeenCalledWith({ id: channel.id });
    expect(dialog.props("channel")).toBeNull();
    expect(snackbar.success).toHaveBeenCalledWith(
      "channels.deleted",
      expect.anything(),
    );
  });

  it("keeps the confirmation open when the delete fails", async () => {
    const channel = channelFixture();
    api.deleteChannel.mockRejectedValue(new Error("offline"));
    const wrapper = mountPanel([channel]);

    const dialog = await askToDelete(wrapper);
    await expect(dialog.props("onConfirm")()).rejects.toThrow("offline");
    await flushPromises();

    expect(dialog.props("channel")).toEqual(channel);
    expect(snackbar.error).toHaveBeenCalled();
  });

  it("counts no slotted upload a snapshot already holds as legacy", async () => {
    const channel = channelFixture({ label: "Main" });
    const adopted = saveFixture({
      id: 7,
      channel_id: channel.id,
      slot: "autosave",
    });
    const wrapper = mountPanel([channel], [adopted], [adopted.id]);

    const dialog = await askToDelete(wrapper);

    expect(wrapper.findComponent(ChannelFan).props("legacySaves")).toEqual([]);
    expect(dialog.props("body")).toBe(
      'channels.delete-body:{"pinned":0,"legacy":0}',
    );
  });

  it("leaves the channel when the delete is canceled", async () => {
    const channel = channelFixture();
    const wrapper = mountPanel([channel]);

    const dialog = await askToDelete(wrapper);
    dialog.vm.$emit("close");
    await flushPromises();

    expect(dialog.props("channel")).toBeNull();
    expect(api.deleteChannel).not.toHaveBeenCalled();
  });

  it("removes a state only once the removal is confirmed", async () => {
    const channel = channelFixture();
    api.pushSnapshot.mockResolvedValue({} as never);
    confirm.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    const wrapper = mountPanel([channel]);
    await openCurrent(wrapper, channel);
    const viewer = wrapper.findComponent(SnapshotViewer);

    viewer.vm.$emit("removeState", "mgba", "auto");
    await flushPromises();
    expect(confirm).toHaveBeenCalledWith(
      expect.objectContaining({ tone: "danger" }),
    );
    expect(api.pushSnapshot).not.toHaveBeenCalled();

    viewer.vm.$emit("removeState", "mgba", "auto");
    await flushPromises();
    expect(api.pushSnapshot).toHaveBeenCalledTimes(1);
  });

  it("offers the viewer's own channels to save a shared snapshot over", async () => {
    const shared = channelFixture({
      id: "0192f1c4-0000-7000-8000-000000000009",
      is_own: false,
      label: "Theirs",
    });
    const mine = channelFixture({ label: "Mine" });
    const wrapper = shallowMount(ChannelsPanel, {
      props: {
        rom: detailedRomFixture({ id: 1, user_channels: [mine, shared] }),
        channels: [shared],
        saves: [],
      },
    });

    await openCurrent(wrapper, shared);

    expect(
      wrapper.findComponent(SnapshotViewer).props("saveOverTargets"),
    ).toEqual([mine]);
  });

  it("stays quiet when a history request fails after it is gone", async () => {
    const channel = channelFixture();
    let fail: (error: Error) => void = () => undefined;
    api.getChannelHistory.mockReturnValue(
      new Promise((_, reject) => {
        fail = reject;
      }) as never,
    );
    const wrapper = mountPanel([channel]);
    wrapper.findComponent(ChannelTile).vm.$emit("open");
    await flushPromises();

    wrapper.unmount();
    fail(new Error("offline"));
    await flushPromises();

    expect(snackbar.error).not.toHaveBeenCalled();
  });

  it("attaches a channel from a removed game to this game's file", async () => {
    const channel = channelFixture();
    const orphan = channelFixture({
      id: "0192f1c4-0000-7000-8000-000000000005",
      label: "Old run",
      rom_id: null,
      rom_file_id: null,
    });
    api.getDetachedChannels.mockResolvedValue({ data: [orphan] } as never);
    api.attachChannel.mockResolvedValue({ data: orphan } as never);
    const wrapper = mountPanel([channel]);
    await flushPromises();

    expect(api.getDetachedChannels).toHaveBeenCalledWith({ platformId: 0 });
    expect(wrapper.find(".r-channels__detached").text()).toContain("Old run");
    await wrapper
      .find(".r-channels__detached")
      .findComponent({ name: "RBtn" })
      .trigger("click");
    await flushPromises();

    expect(api.attachChannel).toHaveBeenCalledWith({
      id: orphan.id,
      romFileId: channel.rom_file_id,
    });
    expect(refetchRom).toHaveBeenCalledWith(1);
    expect(snackbar.success).toHaveBeenCalledWith(
      "channels.attached",
      expect.anything(),
    );
  });
});
