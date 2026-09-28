import { beforeEach, describe, expect, it, vi } from "vitest";
import { type GmeReply, GmeRenderer } from "./gmeRenderer";

// A stand-in for gme.wasm: every rendered frame is left 0.5, right -0.5.
function fakeGme() {
  const memory = new WebAssembly.Memory({ initial: 1 });
  let next = 8;
  const state = { ended: false, deleted: [] as number[] };
  const exports = {
    memory,
    _initialize: vi.fn(),
    malloc: (size: number) => {
      const pointer = next;
      next += size + (8 - (size % 8));
      return pointer;
    },
    free: vi.fn(),
    // A file starting with a zero byte is rejected.
    romm_gme_open: (data: number) =>
      new Uint8Array(memory.buffer)[data] === 0 ? 0 : 7,
    romm_gme_start: vi.fn(() => {
      state.ended = false;
      return 158000;
    }),
    gme_play: (_emu: number, count: number, out: number) => {
      const pcm = new Int16Array(memory.buffer, out, count);
      for (let i = 0; i < count; i += 2) {
        pcm[i] = 16384;
        pcm[i + 1] = -16384;
      }
      return 0;
    },
    gme_seek: vi.fn(),
    gme_tell: () => 1234,
    gme_track_ended: () => (state.ended ? 1 : 0),
    gme_delete: (emu: number) => state.deleted.push(emu),
  };
  return { exports, state };
}

let gme: ReturnType<typeof fakeGme>;
let replies: GmeReply[];

function renderer(sampleRate = 48000) {
  return new GmeRenderer({} as WebAssembly.Module, sampleRate, (reply) =>
    replies.push(reply),
  );
}

/** Render one quantum and return its left channel. */
function quantum(target: GmeRenderer, frames = 4, fill = 0) {
  const left = new Float32Array(frames).fill(fill);
  target.render(left, new Float32Array(frames));
  return left;
}

function load(target: GmeRenderer, bytes = [1, 2, 3], id = 1) {
  target.handle({
    type: "load",
    id,
    data: new Uint8Array(bytes).buffer,
    track: 0,
  });
}

beforeEach(() => {
  gme = fakeGme();
  replies = [];
  vi.spyOn(WebAssembly, "Instance").mockImplementation(function () {
    return { exports: gme.exports };
  });
});

describe("GmeRenderer", () => {
  it("reports the track length once a file loads", () => {
    const target = renderer();

    load(target, [1, 2, 3], 4);

    expect(replies).toEqual([{ type: "loaded", id: 4, durationMs: 158000 }]);
  });

  it("reports an error for a file libgme rejects", () => {
    const target = renderer();

    load(target, [0, 1]);

    expect(replies).toEqual([{ type: "error", id: 1 }]);
  });

  it("outputs silence until told to play, then the rendered samples", () => {
    const target = renderer();
    load(target);
    const left = new Float32Array(4).fill(1);
    const right = new Float32Array(4).fill(1);

    target.render(left, right);
    expect([...left, ...right]).toEqual(new Array(8).fill(0));

    target.handle({ type: "play" });
    target.render(left, right);
    expect([...left]).toEqual([0.5, 0.5, 0.5, 0.5]);
    expect([...right]).toEqual([-0.5, -0.5, -0.5, -0.5]);
  });

  it("reports the position about four times a second", () => {
    const target = renderer(1024);
    load(target);
    target.handle({ type: "play" });
    replies = [];

    quantum(target, 128);
    expect(replies).toEqual([]);
    quantum(target, 128);
    expect(replies).toEqual([{ type: "time", id: 1, ms: 1234 }]);
  });

  it("stops and reports the end of the track", () => {
    const target = renderer();
    load(target);
    target.handle({ type: "play" });
    replies = [];
    gme.state.ended = true;

    quantum(target);
    const left = quantum(target, 4, 1);

    expect(replies.map((reply) => reply.type)).toEqual(["time", "ended"]);
    expect([...left]).toEqual([0, 0, 0, 0]);
  });

  it("starts an ended track over when told to play again", () => {
    const target = renderer();
    load(target);
    target.handle({ type: "play" });
    gme.state.ended = true;
    quantum(target);
    replies = [];

    target.handle({ type: "play" });
    const left = quantum(target);

    expect(gme.exports.romm_gme_start).toHaveBeenCalledTimes(2);
    expect(replies).toEqual([{ type: "time", id: 1, ms: 1234 }]);
    expect([...left]).toEqual([0.5, 0.5, 0.5, 0.5]);
  });

  it("restarts the track to seek backwards, so its fade survives", () => {
    const target = renderer();
    load(target);

    target.handle({ type: "seek", ms: 500 });
    quantum(target);

    expect(gme.exports.romm_gme_start).toHaveBeenCalledTimes(2);
    expect(gme.exports.gme_seek).toHaveBeenCalledWith(7, 500);
    expect(replies.at(-1)).toEqual({ type: "time", id: 1, ms: 1234 });
  });

  it("seeks forwards without restarting the track", () => {
    const target = renderer();
    load(target);

    target.handle({ type: "seek", ms: 5000 });
    quantum(target);

    expect(gme.exports.romm_gme_start).toHaveBeenCalledTimes(1);
    expect(gme.exports.gme_seek).toHaveBeenCalledWith(7, 5000);
  });

  it("collapses a scrub into one seek per quantum", () => {
    const target = renderer();
    load(target);

    for (const ms of [2000, 3000, 4000]) target.handle({ type: "seek", ms });
    expect(gme.exports.gme_seek).not.toHaveBeenCalled();
    quantum(target);

    expect(gme.exports.gme_seek).toHaveBeenCalledTimes(1);
    expect(gme.exports.gme_seek).toHaveBeenCalledWith(7, 4000);
  });

  it("frees the previous track when another loads", () => {
    const target = renderer();
    load(target, [1], 1);
    load(target, [1], 2);

    expect(gme.state.deleted).toEqual([7]);
    expect(replies.at(-1)).toEqual({
      type: "loaded",
      id: 2,
      durationMs: 158000,
    });
  });
});
