import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { ChannelSchema } from "@/__generated__";
import { saveFixture } from "@/utils/assets.fixtures";
import {
  channelFixture,
  snapshotFixture,
  stateFixture,
} from "@/v2/utils/snapshots.fixtures";
import SnapshotViewer, { type ViewerTarget } from "./SnapshotViewer.vue";

vi.mock("vue-i18n");

const RDrawer = {
  template: `<div><slot name="header" /><slot /><slot name="footer" /></div>`,
};
const RMenu = {
  template: `<div class="menu"><slot name="activator" :props="{}" /><slot /></div>`,
};

function mountViewer(target: ViewerTarget, copyTargets: ChannelSchema[] = []) {
  return mount(SnapshotViewer, {
    props: { target, copyTargets },
    global: { stubs: { RDrawer, RMenu, RImg: true, RTooltip: true } },
  });
}

/** A button or menu item, by its visible text or, for icon buttons, its aria-label. */
function button(wrapper: ReturnType<typeof mountViewer>, key: string) {
  return wrapper
    .findAll("button, [role=menuitem]")
    .find((b) => b.text() === key || b.attributes("aria-label") === key);
}

function primaryLabel(wrapper: ReturnType<typeof mountViewer>) {
  return wrapper.find(".r-snapshot-viewer__primary").text();
}

const older = snapshotFixture({ id: 40 });

describe("SnapshotViewer", () => {
  it("offers restore and pin on an older snapshot of an own channel", async () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture(),
      snapshot: older,
    });

    await button(wrapper, "channels.restore")?.trigger("click");
    await button(wrapper, "channels.pin")?.trigger("click");

    expect(wrapper.emitted("restore")).toHaveLength(1);
    expect(wrapper.emitted("togglePin")).toHaveLength(1);
  });

  it("leads with restore on an older snapshot", () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture(),
      snapshot: older,
    });

    expect(primaryLabel(wrapper)).toBe("channels.restore");
  });

  it("leads with download on the current snapshot, which has nothing to restore", () => {
    const channel = channelFixture();
    const wrapper = mountViewer({
      kind: "snapshot",
      channel,
      snapshot: channel.current ?? older,
    });

    expect(button(wrapper, "channels.restore")).toBeUndefined();
    expect(primaryLabel(wrapper)).toBe("channels.download");
  });

  it("removes one bank slot by core and slot", async () => {
    const channel = channelFixture();
    const wrapper = mountViewer({
      kind: "snapshot",
      channel,
      snapshot: snapshotFixture({
        states: {
          snes9x: { auto: stateFixture("a1"), "3": stateFixture("b22") },
        },
      }),
    });

    const remove = wrapper
      .findAll("button")
      .filter((b) =>
        b.attributes("aria-label")?.startsWith("channels.remove-state-named"),
      );
    expect(remove).toHaveLength(2);
    await remove[0]?.trigger("click");

    expect(wrapper.emitted("removeState")?.[0]).toEqual(["snes9x", "auto"]);
  });

  it("lists the auto slot first, then numbered slots in order", () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture(),
      snapshot: snapshotFixture({
        states: {
          snes9x: {
            "10": stateFixture("a1"),
            "2": stateFixture("b22"),
            auto: stateFixture("c333"),
          },
        },
      }),
    });

    expect(
      wrapper.findAll(".r-snapshot-viewer__slot-name").map((n) => n.text()),
    ).toEqual([
      "channels.slot-auto",
      'channels.slot-n:{"slot":"2"}',
      'channels.slot-n:{"slot":"10"}',
    ]);
  });

  it("leaves another user's private channel read-only", () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture({ is_own: false, is_public: false }),
      snapshot: older,
    });

    expect(button(wrapper, "channels.restore")).toBeUndefined();
    expect(button(wrapper, "channels.pin")).toBeUndefined();
    expect(
      wrapper.find('[aria-label^="channels.remove-state-named"]').exists(),
    ).toBe(false);
    expect(button(wrapper, "channels.fork")).toBeDefined();
    expect(button(wrapper, "channels.download")).toBeDefined();
  });

  it("lets anyone restore into a shared channel", () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture({ is_own: false, is_public: true }),
      snapshot: older,
    });

    expect(button(wrapper, "channels.restore")).toBeDefined();
  });

  it("offers copy-over only when another channel shares the file", async () => {
    const target: ViewerTarget = {
      kind: "snapshot",
      channel: channelFixture(),
      snapshot: older,
    };
    const copyOver = 'channels.copy-over-named:{"label":"Speedrun"}';
    expect(button(mountViewer(target), copyOver)).toBeUndefined();

    const other = channelFixture({ id: "other", label: "Speedrun" });
    const wrapper = mountViewer(target, [other]);
    await button(wrapper, copyOver)?.trigger("click");

    expect(wrapper.emitted("copyOver")?.[0]).toEqual([other]);
  });

  it("explains an empty hardcore bank", () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture({ is_hardcore: true }),
      snapshot: snapshotFixture({ is_hardcore: true, states: {} }),
    });

    expect(wrapper.text()).toContain("channels.hardcore-no-states");
  });

  it("turns an own legacy save into a snapshot", async () => {
    const wrapper = mountViewer({
      kind: "save",
      channel: channelFixture(),
      save: saveFixture({ id: 9, slot: "autosave" }),
    });

    await button(wrapper, "channels.make-snapshot")?.trigger("click");

    expect(wrapper.emitted("makeSnapshot")).toHaveLength(1);
  });

  it("downloads the save a snapshot holds", async () => {
    const wrapper = mountViewer({
      kind: "snapshot",
      channel: channelFixture(),
      snapshot: older,
    });

    await button(wrapper, "channels.download")?.trigger("click");

    expect(wrapper.emitted("download")?.[0]).toEqual([
      older.save?.download_path,
      older.save?.file_name,
    ]);
  });
});
