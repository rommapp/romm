import { AxiosError } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { responseError } from "@/test-utils/serverError";
import { saveContentHash } from "@/utils/saveSync/hash";
import {
  channelFixture,
  snapshotFixture,
  bankStateFixture,
} from "@/utils/snapshots.fixtures";
import {
  buildPush,
  heldPushSender,
  sendPush,
  sessionTarget,
  SnapshotSession,
  type SnapshotContent,
  type SnapshotTarget,
} from "./snapshotSession";

const api = vi.hoisted(() => ({ pushSnapshot: vi.fn() }));
vi.mock("@/services/api/snapshot", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api/snapshot")>()),
  default: api,
}));

const UUID_V7 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const SRAM = new Uint8Array([1, 2, 3]).buffer;
const STATE = new Uint8Array([7, 7]).buffer;

function file(bytes: ArrayBuffer, fileName = "game.srm") {
  return { bytes, fileName };
}

function conflict(data: unknown): AxiosError {
  return responseError(409, data);
}

const parentGone = () =>
  responseError(404, { detail: "Parent snapshot not found" });

const target: SnapshotTarget = {
  romFileId: 7,
  channelId: "chan",
  label: "default",
  expectedCurrentId: 42,
  parentSnapshotId: null,
  bank: { mgba: { auto: "a1b2", "1": "c3d4" } },
  saveHash: saveContentHash(new Uint8Array(SRAM)),
  core: "mgba",
  emulatorVersion: "4.2.3",
};

describe("sessionTarget", () => {
  const rom = (channels = [channelFixture()]) => ({
    channel_file_id: 7,
    user_channels: channels,
  });

  it("builds on the booted snapshot and expects the channel's current", () => {
    const channel = channelFixture({ current_snapshot_id: 50 });
    const booted = snapshotFixture({
      id: 30,
      channel_id: channel.id,
    });

    const result = sessionTarget({
      rom: rom([channel]),
      core: "snes9x",
      snapshot: booted,
      slot: "autosave",
    });

    expect(result).toMatchObject({
      channelId: channel.id,
      expectedCurrentId: 50,
      parentSnapshotId: 30,
      bank: { snes9x: { auto: "a1b2" } },
      saveHash: "9f2c",
    });
  });

  it("writes to the channel of the save it booted", () => {
    const other = channelFixture({ id: "other", label: "speedrun" });

    const result = sessionTarget({
      rom: rom([channelFixture(), other]),
      core: "snes9x",
      save: { channel_id: "other" },
      slot: "autosave",
    });

    expect(result).toMatchObject({ channelId: "other", label: "speedrun" });
  });

  it("files the autosave slot under the default channel", () => {
    const result = sessionTarget({
      rom: rom(),
      core: "snes9x",
      slot: "autosave",
    });

    expect(result).toMatchObject({
      channelId: channelFixture().id,
      expectedCurrentId: 42,
      parentSnapshotId: null,
    });
  });

  it("mints the id of a channel the first push creates", () => {
    const result = sessionTarget({
      rom: rom(),
      core: "snes9x",
      slot: "Speedrun",
    });

    expect(result).toMatchObject({
      romFileId: 7,
      channelId: expect.stringMatching(UUID_V7),
      label: "Speedrun",
      expectedCurrentId: null,
      bank: {},
      saveHash: null,
    });
  });

  it("never writes into another user's channel", () => {
    const shared = channelFixture({ is_own: false });

    const result = sessionTarget({
      rom: rom([shared]),
      core: "snes9x",
      save: { channel_id: shared.id },
      slot: "autosave",
    });

    expect(result?.channelId).not.toBe(shared.id);
    expect(result).toMatchObject({ label: "default" });
  });

  it("has nowhere to write without a channel file", () => {
    expect(
      sessionTarget({
        rom: { channel_file_id: null, user_channels: [] },
        core: "snes9x",
        slot: "autosave",
      }),
    ).toBeNull();
  });
});

describe("buildPush", () => {
  it("sends a save with its hash, carrying the parent's bank", () => {
    const push = buildPush(target, { kind: "save", save: file(SRAM) });

    expect(push.manifest).toEqual({
      rom_file_id: 7,
      expected_current_id: 42,
      channel_id: "chan",
      label: "default",
      emulator: "mgba",
      core: "mgba",
      emulator_version: "4.2.3",
      save: {
        hash: saveContentHash(new Uint8Array(SRAM)),
        shape: "SINGLE",
        format: "native",
      },
    });
    expect(push.files.map((f) => f.key)).toEqual(["save"]);
  });

  it("files a state in its slot beside the parent's other slots", () => {
    const content: SnapshotContent = {
      kind: "state",
      slot: "auto",
      state: file(STATE, "game.state"),
      save: file(SRAM),
    };

    const push = buildPush(target, content);

    expect(push.manifest.states).toEqual({
      mgba: { auto: saveContentHash(new Uint8Array(STATE)), "1": "c3d4" },
    });
    expect(push.manifest.save).toBeUndefined();
    expect(push.files.map((f) => f.key)).toEqual(["state:mgba:auto"]);
  });

  it("sends the SRAM beside a state when the parent holds another", () => {
    const push = buildPush(
      { ...target, saveHash: "other" },
      {
        kind: "state",
        slot: "0",
        state: file(STATE, "game.state"),
        save: file(SRAM),
      },
    );

    expect(push.manifest.save).toMatchObject({ shape: "SINGLE" });
    expect(push.files.map((f) => f.key)).toEqual(["save", "state:mgba:0"]);
  });

  it("names the channel to create and the snapshot it starts from", () => {
    const push = buildPush(
      { ...target, channelId: "new", label: "speedrun", parentSnapshotId: 9 },
      { kind: "save", save: file(SRAM) },
    );

    expect(push.manifest).toMatchObject({
      channel_id: "new",
      label: "speedrun",
      parent_snapshot_id: 9,
    });
  });
});

describe("heldPushSender", () => {
  const content: SnapshotContent = { kind: "save", save: file(SRAM) };
  const sentManifest = (call: number) =>
    api.pushSnapshot.mock.calls[call]![0].manifest;

  beforeEach(() => {
    api.pushSnapshot.mockReset();
  });

  it("expects the current the push held before it made", async () => {
    api.pushSnapshot
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 43 }) })
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 44 }) });
    const send = heldPushSender();

    await send({ target, content });
    await send({ target, content });

    expect(sentManifest(1)).toMatchObject({ expected_current_id: 43 });
    expect(sentManifest(1)).not.toHaveProperty("parent_snapshot_id");
  });

  it("builds on the branch the push held before it was kept as", async () => {
    const branch = snapshotFixture({ id: 60, kind: "branch" });
    api.pushSnapshot
      .mockRejectedValueOnce(conflict({ current: { id: 55 }, branch }))
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 61 }) });
    const send = heldPushSender();

    await send({ target, content });
    await send({ target, content });

    expect(sentManifest(1)).toMatchObject({
      expected_current_id: 42,
      parent_snapshot_id: 60,
    });
  });

  it("sends a push held on another base as it was held", async () => {
    api.pushSnapshot.mockResolvedValue({ data: snapshotFixture({ id: 43 }) });
    const send = heldPushSender();

    await send({ target, content });
    await send({ target: { ...target, expectedCurrentId: 50 }, content });

    expect(sentManifest(1)).toMatchObject({ expected_current_id: 50 });
  });
});

describe("SnapshotSession", () => {
  beforeEach(() => {
    api.pushSnapshot.mockReset();
  });

  it("builds each push on the snapshot the last one made", async () => {
    const first = snapshotFixture({
      id: 43,
      states: { mgba: { auto: bankStateFixture("e5f6") } },
    });
    api.pushSnapshot
      .mockResolvedValueOnce({ data: first })
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 44 }) });
    const session = new SnapshotSession(target, "device-1");

    await Promise.all([
      session.push({ kind: "save", save: file(SRAM) }),
      session.push({
        kind: "state",
        slot: "0",
        state: file(STATE, "game.state"),
        save: null,
      }),
    ]);

    const [firstCall, secondCall] = api.pushSnapshot.mock.calls;
    expect(firstCall![0]).toMatchObject({
      manifest: { expected_current_id: 42 },
      deviceId: "device-1",
    });
    expect(secondCall![0].manifest).toMatchObject({
      expected_current_id: 43,
      states: { mgba: { auto: "e5f6", "0": expect.any(String) } },
    });
  });

  it("chains later pushes on the branch once the channel moved on", async () => {
    const branch = snapshotFixture({ id: 60, kind: "branch" });
    api.pushSnapshot
      .mockRejectedValueOnce(conflict({ current: { id: 55 }, branch }))
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 61 }) });
    const session = new SnapshotSession(target);

    const outcome = await session.push({ kind: "save", save: file(SRAM) });
    await session.push({ kind: "save", save: file(SRAM) });

    expect(outcome).toEqual({
      kind: "branched",
      snapshot: branch,
      reason: "moved",
    });
    expect(api.pushSnapshot.mock.calls[1]![0].manifest).toMatchObject({
      expected_current_id: 42,
      parent_snapshot_id: 60,
    });
  });

  it("files every push of a new channel under one channel id", async () => {
    api.pushSnapshot.mockRejectedValue(new Error("offline"));
    const fresh = sessionTarget({
      rom: { channel_file_id: 7, user_channels: [] },
      core: "mgba",
      slot: "autosave",
    })!;
    const session = new SnapshotSession(fresh);
    const content: SnapshotContent = { kind: "save", save: file(SRAM) };

    const held = [session.hold(content), session.hold(content)];
    await expect(session.push(content)).rejects.toThrow("offline");

    const sent = api.pushSnapshot.mock.calls[0]![0].manifest.channel_id;
    expect(sent).toMatch(UUID_V7);
    expect(held.map((push) => push.target.channelId)).toEqual([sent, sent]);
  });

  it("keeps building on its target after a failed push", async () => {
    api.pushSnapshot
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 43 }) });
    const session = new SnapshotSession(target);

    await expect(
      session.push({ kind: "save", save: file(SRAM) }),
    ).rejects.toThrow("offline");
    await session.push({ kind: "save", save: file(SRAM) });

    expect(api.pushSnapshot.mock.calls[1]![0].manifest).toMatchObject({
      expected_current_id: 42,
    });
  });
});

describe("sendPush", () => {
  beforeEach(() => {
    api.pushSnapshot.mockReset();
  });

  it("builds on the current when retention removed the parent", async () => {
    api.pushSnapshot
      .mockRejectedValueOnce(parentGone())
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 50 }) });

    const outcome = await sendPush(
      buildPush(
        { ...target, parentSnapshotId: 9 },
        { kind: "save", save: file(SRAM) },
      ),
    );

    const retried = api.pushSnapshot.mock.calls[1]![0].manifest;
    expect(outcome.kind).toBe("current");
    expect(retried.parent_snapshot_id).toBeUndefined();
    expect(retried.expected_current_id).toBe(42);
  });

  it("lands as a branch once the current is gone too", async () => {
    api.pushSnapshot
      .mockRejectedValueOnce(parentGone())
      .mockRejectedValueOnce(parentGone())
      .mockResolvedValueOnce({ data: snapshotFixture({ id: 51 }) });

    await sendPush(
      buildPush(
        { ...target, parentSnapshotId: 9 },
        { kind: "save", save: file(SRAM) },
      ),
    );

    expect(api.pushSnapshot.mock.calls[2]![0].manifest).toMatchObject({
      expected_current_id: null,
    });
  });

  it("drops carried states the server no longer holds, keeping its own", async () => {
    api.pushSnapshot
      .mockRejectedValueOnce(responseError(400, { missing: ["state:mgba:1"] }))
      .mockResolvedValueOnce({ data: snapshotFixture() });

    await sendPush(
      buildPush(target, {
        kind: "state",
        slot: "0",
        state: file(STATE, "game.state"),
        save: null,
      }),
    );

    const states = api.pushSnapshot.mock.calls[1]![0].manifest.states;
    expect(Object.keys(states.mgba).sort()).toEqual(["0", "auto"]);
  });

  it("lands as a branch on the current when a hardcore channel refuses it", async () => {
    const branch = snapshotFixture({ id: 52, kind: "branch" });
    api.pushSnapshot
      .mockRejectedValueOnce(responseError(409, { hardcore_downgrade: true }))
      .mockRejectedValueOnce(conflict({ current: { id: 42 }, branch }));

    const outcome = await sendPush(
      buildPush(target, { kind: "save", save: file(SRAM) }),
    );

    expect(outcome).toEqual({
      kind: "branched",
      snapshot: branch,
      reason: "hardcore",
    });
    expect(api.pushSnapshot.mock.calls[1]![0].manifest).toMatchObject({
      expected_current_id: null,
      parent_snapshot_id: 42,
    });
  });

  it("gives up when content it sends itself is called missing", async () => {
    api.pushSnapshot.mockRejectedValue(
      responseError(400, { missing: ["state:mgba:0"] }),
    );

    await expect(
      sendPush(
        buildPush(target, {
          kind: "state",
          slot: "0",
          state: file(STATE, "game.state"),
          save: null,
        }),
      ),
    ).rejects.toBeInstanceOf(AxiosError);
    expect(api.pushSnapshot).toHaveBeenCalledOnce();
  });

  it("passes on a 409 that kept nothing", async () => {
    api.pushSnapshot.mockRejectedValue(conflict({ hardcore_downgrade: true }));

    await expect(
      sendPush(buildPush(target, { kind: "save", save: file(SRAM) })),
    ).rejects.toBeInstanceOf(AxiosError);
  });

  it("sends each file with its screenshot under the part's name", async () => {
    api.pushSnapshot.mockResolvedValue({ data: snapshotFixture() });
    const shot = new Uint8Array([9]).buffer;

    await sendPush(
      buildPush(target, {
        kind: "save",
        save: { ...file(SRAM), screenshot: shot, screenshotName: "game.png" },
      }),
    );

    const [part] = api.pushSnapshot.mock.calls[0]![0].parts;
    expect(part.key).toBe("save");
    expect(part.file.name).toBe("game.srm");
    expect(part.screenshot.name).toBe("game.png");
  });
});
