import { describe, expect, it } from "vitest";
import type { ChannelSchema } from "@/__generated__";
import {
  bankOf,
  channelLabelForSlot,
  copySaveManifest,
  saveOverTargets,
  forkManifest,
  restoreManifest,
  saveDataCounts,
  snapshotBadges,
  withoutStateManifest,
} from "@/v2/utils/snapshots";
import {
  channelFixture,
  snapshotFixture,
  stateFixture,
} from "@/v2/utils/snapshots.fixtures";

const snapshot = snapshotFixture({
  id: 40,
  states: {
    snes9x: { auto: stateFixture("a1"), "3": stateFixture("b2") },
    bsnes: { auto: stateFixture("c3") },
  },
});

function channel(over: Partial<ChannelSchema> = {}): ChannelSchema {
  return channelFixture({
    id: "ch-1",
    rom_file_id: 7,
    current_snapshot_id: 42,
    ...over,
  });
}

describe("snapshot manifests", () => {
  it("reads a bank as the hashes a manifest names", () => {
    expect(bankOf(snapshot)).toEqual({
      snes9x: { auto: "a1", "3": "b2" },
      bsnes: { auto: "c3" },
    });
  });

  it("restores a snapshot on top of the channel's current", () => {
    expect(restoreManifest(snapshot, channel())).toEqual({
      rom_file_id: 7,
      channel_id: "ch-1",
      expected_current_id: 42,
      parent_snapshot_id: 40,
    });
  });

  it("drops one slot and leaves the other cores to carry over", () => {
    expect(withoutStateManifest(snapshot, channel(), "snes9x", "3")).toEqual({
      rom_file_id: 7,
      channel_id: "ch-1",
      expected_current_id: 42,
      parent_snapshot_id: 40,
      states: { snes9x: { auto: "a1" } },
    });
  });

  it("empties a core when its last slot goes", () => {
    const manifest = withoutStateManifest(snapshot, channel(), "bsnes", "auto");

    expect(manifest?.states).toEqual({ bsnes: {} });
  });

  it("saves over a channel expecting that channel's current", () => {
    const target = channel({ id: "ch-2", current_snapshot_id: 9 });

    expect(restoreManifest(snapshot, target)).toMatchObject({
      channel_id: "ch-2",
      expected_current_id: 9,
      parent_snapshot_id: 40,
    });
  });

  it("forks into a new channel that starts empty", () => {
    expect(forkManifest(snapshot, 7, "Speedrun")).toEqual({
      rom_file_id: 7,
      label: "Speedrun",
      expected_current_id: null,
      parent_snapshot_id: 40,
    });
  });

  it("keeps a hardcore snapshot hardcore wherever it is restored or copied", () => {
    const hardcore = snapshotFixture({ id: 40, is_hardcore: true });

    expect(restoreManifest(hardcore, channel())?.is_hardcore).toBe(true);
    expect(forkManifest(hardcore, 7, "Speedrun").is_hardcore).toBe(true);
    expect(restoreManifest(snapshot, channel())?.is_hardcore).toBeUndefined();
  });

  it("copies a loose save in by id", () => {
    expect(copySaveManifest({ id: 1907 }, channel())).toMatchObject({
      save: { copy_of: 1907 },
      expected_current_id: 42,
    });
  });

  it("refuses a push into a channel whose file is gone", () => {
    expect(restoreManifest(snapshot, channel({ rom_file_id: null }))).toBe(
      null,
    );
  });

  it("offers only the user's other channels on the same file", () => {
    const from = channel();
    const all = [
      from,
      channel({ id: "same-file" }),
      channel({ id: "other-file", rom_file_id: 8 }),
      channel({ id: "not-mine", is_own: false }),
    ];

    expect(saveOverTargets(all, from).map((c) => c.id)).toEqual(["same-file"]);
  });
});

describe("snapshotBadges", () => {
  const t = (key: string) => key;

  it("marks the current, a branch, a pin and hardcore in that order", () => {
    const marked = snapshotFixture({
      id: 42,
      kind: "branch",
      pin_count: 1,
      is_hardcore: true,
    });

    expect(snapshotBadges(marked, channel(), t)).toEqual([
      { label: "channels.current", color: "primary" },
      { label: "channels.branch", outlined: true },
      { label: "channels.pinned", color: "accent" },
      { label: "channels.hardcore", color: "warning" },
    ]);
  });

  it("gives a plain past snapshot no badge", () => {
    expect(snapshotBadges(snapshot, channel(), t)).toEqual([]);
  });
});

describe("saveDataCounts", () => {
  it("counts backups and channels, not the rows channels hold", () => {
    expect(
      saveDataCounts({
        saves: [{ channel_id: null }, { channel_id: "ch-1" }],
        states: [{ channel_id: null }, { channel_id: "ch-1" }],
        channels: [channel()],
      }),
    ).toEqual({ saves: 2, states: 1 });
  });
});

describe("channelLabelForSlot", () => {
  it("files a tagged slot under its untagged channel", () => {
    expect(channelLabelForSlot("Run [2026-01-01_00-00-00]")).toBe("Run");
    expect(channelLabelForSlot("Run [2026-01-01_00-00-00-123]")).toBe("Run");
  });

  it("files autosave under the default channel", () => {
    expect(channelLabelForSlot("Autosave")).toBe("default");
  });
});
