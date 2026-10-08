import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { saveFixture } from "@/utils/assets.fixtures";
import { hoursAgo } from "@/v2/utils/saveStates.fixtures";
import { channelFixture, snapshotFixture } from "@/v2/utils/snapshots.fixtures";
import ChannelTimeline from "./ChannelTimeline.vue";

vi.mock("vue-i18n");

const main = channelFixture({ label: "Main", current_snapshot_id: 3 });
const speedrun = channelFixture({
  id: "0192f1c4-0000-7000-8000-000000000002",
  label: "Speedrun",
  current_snapshot_id: 4,
});
const root = snapshotFixture({
  id: 1,
  parent_snapshot_id: null,
  created_at: hoursAgo(10),
});
const next = snapshotFixture({
  id: 3,
  parent_snapshot_id: 1,
  created_at: hoursAgo(5),
});
const fork = snapshotFixture({
  id: 4,
  parent_snapshot_id: 1,
  created_at: hoursAgo(2),
});
const legacy = saveFixture({
  id: 9,
  channel_id: main.id,
  slot: "autosave",
  updated_at: hoursAgo(1),
});

function mountTimeline() {
  return mount(ChannelTimeline, {
    props: {
      channels: [main, speedrun],
      histories: { [main.id]: [next, root], [speedrun.id]: [fork] },
      legacySaves: { [main.id]: [legacy] },
    },
  });
}

describe("ChannelTimeline", () => {
  it("orders every channel's points newest first", () => {
    const labels = mountTimeline()
      .findAll('[role="button"]')
      .map((node) => node.attributes("aria-label")?.split(",")[0]);

    expect(labels).toEqual([
      "Main · channels.legacy-save",
      "Speedrun",
      "Main",
      "Main",
    ]);
  });

  it("draws an edge from each parent, across lanes for a fork", () => {
    const edges = mountTimeline().findAll("path");

    expect(edges).toHaveLength(2);
    const startXs = edges.map((e) => e.attributes("d")?.split(",")[0]);
    expect(new Set(startXs).size).toBe(1);
  });

  it("arcs a restore around the abandoned snapshots and greys them out", () => {
    const channel = channelFixture({ label: "Main", current_snapshot_id: 13 });
    const loaded = snapshotFixture({
      id: 11,
      parent_snapshot_id: null,
      created_at: hoursAgo(9),
    });
    const abandoned = snapshotFixture({
      id: 12,
      parent_snapshot_id: 11,
      created_at: hoursAgo(6),
    });
    const restored = snapshotFixture({
      id: 13,
      parent_snapshot_id: 11,
      created_at: hoursAgo(3),
    });
    const wrapper = mount(ChannelTimeline, {
      props: {
        channels: [channel],
        histories: { [channel.id]: [restored, abandoned, loaded] },
        legacySaves: {},
      },
    });

    const greyed = wrapper
      .findAll('[role="button"]')
      .map((node) =>
        node.classes().includes("r-channel-timeline__node--abandoned"),
      );
    const bulges = wrapper.findAll("path").map((path) => {
      const [, startX, controlX] = path
        .attributes("d")!
        .match(/^M([\d.]+),[\d.]+ C([\d.-]+),/)!;
      return Number(controlX) < Number(startX);
    });

    expect(greyed).toEqual([false, true, false]);
    expect(bulges.filter(Boolean)).toHaveLength(1);
  });

  it("colors each channel by its age, whatever order it is listed in", () => {
    const older = channelFixture({ label: "Older", created_at: hoursAgo(48) });
    const newer = channelFixture({
      id: "0192f1c4-0000-7000-8000-000000000003",
      label: "Newer",
      created_at: hoursAgo(1),
    });
    const colorOf = (channels: (typeof older)[]) =>
      mount(ChannelTimeline, {
        props: {
          channels,
          histories: {
            [older.id]: [snapshotFixture({ id: 21, created_at: hoursAgo(3) })],
            [newer.id]: [snapshotFixture({ id: 22, created_at: hoursAgo(2) })],
          },
          legacySaves: {},
        },
      })
        .findAll('[role="button"]')
        .map((node) => node.find("circle").attributes("stroke"));

    expect(colorOf([newer, older])).toEqual(colorOf([older, newer]));
    expect(colorOf([newer, older])[1]).toBe("var(--r-color-brand-primary)");
  });

  it("opens a point with Enter", async () => {
    const wrapper = mountTimeline();
    const nodes = wrapper.findAll('[role="button"]');

    await nodes[1]?.trigger("keydown", { key: "Enter" });
    await nodes[0]?.trigger("click");

    expect(wrapper.emitted("openSnapshot")?.[0]).toEqual([speedrun, fork]);
    expect(wrapper.emitted("openSave")?.[0]).toEqual([main, legacy]);
  });
});
