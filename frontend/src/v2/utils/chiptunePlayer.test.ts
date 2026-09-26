import { gzipSync } from "node:zlib";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChiptunePlayer } from "./chiptunePlayer";

vi.mock("./gmeAudioWorklet.js?url", () => ({ default: "/worklet.js" }));

type Posted = { type: string; id?: number; data?: ArrayBuffer; ms?: number };

class FakePort {
  onmessage: ((event: MessageEvent) => void) | null = null;
  posted: Posted[] = [];

  postMessage(message: Posted) {
    this.posted.push(message);
  }

  /** Stand in for the worklet replying. */
  reply(message: object) {
    this.onmessage?.({ data: message } as MessageEvent);
  }

  types() {
    return this.posted.map((message) => message.type);
  }

  lastLoad() {
    return this.posted.filter((message) => message.type === "load").at(-1);
  }
}

const NSF_BYTES = new Uint8Array([0x4e, 0x45, 0x53, 0x4d, 0x1a, 0x01]);

let port: FakePort;
const addModule = vi.fn(async () => {});
const resume = vi.fn(async () => {});
const gain = { gain: { value: -1 }, connect: vi.fn() };
let bodies: Map<string, Uint8Array>;

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function loaded(player: ChiptunePlayer, durationMs = 158000) {
  await player.load("/track.nsf");
  const id = port.lastLoad()?.id;
  port.reply({ type: "loaded", id, durationMs });
  await flush();
  return id;
}

function recordEvents(player: ChiptunePlayer) {
  const events: string[] = [];
  for (const name of [
    "play",
    "pause",
    "ended",
    "timeupdate",
    "loadedmetadata",
    "canplay",
    "error",
  ]) {
    player.addEventListener(name, () => events.push(name));
  }
  return events;
}

beforeEach(() => {
  vi.clearAllMocks();
  port = new FakePort();
  gain.gain.value = -1;
  bodies = new Map([
    ["/assets/gme/gme.wasm", new Uint8Array([0, 97, 115, 109])],
    ["/track.nsf", NSF_BYTES],
  ]);

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = bodies.get(url);
      return body
        ? new Response(body.slice())
        : new Response(null, { status: 404 });
    }),
  );
  vi.spyOn(WebAssembly, "compile").mockResolvedValue({} as WebAssembly.Module);
  vi.stubGlobal(
    "AudioContext",
    class {
      audioWorklet = { addModule };
      destination = {};
      resume = resume;
      close = vi.fn(async () => {});
      createGain() {
        return gain;
      }
    },
  );
  vi.stubGlobal(
    "AudioWorkletNode",
    class {
      port = port;
      connect = vi.fn(() => gain);
    },
  );
});

describe("ChiptunePlayer", () => {
  it("hands the file to the worklet and reports the track length", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await loaded(player);

    const load = port.lastLoad();
    expect(new Uint8Array(load?.data ?? new ArrayBuffer(0))).toEqual(NSF_BYTES);
    expect(player.duration).toBe(158);
    expect(events).toEqual(["loadedmetadata", "canplay"]);
  });

  it("gunzips a VGZ file before handing it over", async () => {
    bodies.set("/track.nsf", new Uint8Array(gzipSync(NSF_BYTES)));
    const player = new ChiptunePlayer();

    await player.load("/track.nsf");

    const data = port.lastLoad()?.data ?? new ArrayBuffer(0);
    expect(new Uint8Array(data)).toEqual(NSF_BYTES);
  });

  it("starts the worklet only once a play asked for early has a track", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    const loading = player.load("/track.nsf");
    await player.play();
    await loading;
    expect(events).toEqual(["play"]);
    expect(port.types()).not.toContain("play");

    port.reply({ type: "loaded", id: port.lastLoad()?.id, durationMs: 1000 });
    await flush();

    expect(player.paused).toBe(false);
    expect(port.types()).toContain("play");
  });

  it("drops replies about a track that was replaced", async () => {
    const player = new ChiptunePlayer();
    const staleId = await loaded(player);
    const events = recordEvents(player);

    await player.load("/track.nsf");
    port.reply({ type: "time", id: staleId, ms: 5000 });
    port.reply({ type: "ended", id: staleId });

    expect(events).toEqual([]);
    expect(player.currentTime).toBe(0);
  });

  it("tracks the position and stops at the end of the track", async () => {
    const player = new ChiptunePlayer();
    const id = await loaded(player);
    await player.play();
    const events = recordEvents(player);

    port.reply({ type: "time", id, ms: 2500 });
    port.reply({ type: "ended", id });

    expect(player.currentTime).toBe(2.5);
    expect(player.paused).toBe(true);
    expect(events).toEqual(["timeupdate", "ended"]);
  });

  it("forwards seeks to the worklet in milliseconds", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);

    player.currentTime = 42;
    await flush();

    expect(port.posted.at(-1)).toEqual({ type: "seek", ms: 42000 });
    expect(player.currentTime).toBe(42);
  });

  it("applies volume and mute to the output gain", async () => {
    const player = new ChiptunePlayer();
    player.volume = 0.4;
    await loaded(player);
    expect(gain.gain.value).toBe(0.4);

    player.muted = true;
    expect(gain.gain.value).toBe(0);

    player.muted = false;
    expect(gain.gain.value).toBe(0.4);
  });

  it("fires error when the file can't be fetched", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);
    vi.spyOn(console, "error").mockImplementation(() => {});

    await player.load("/missing.nsf");

    expect(events).toEqual(["error"]);
  });

  it("fires error when the worklet rejects the file", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/track.nsf");
    port.reply({ type: "error", id: port.lastLoad()?.id });

    expect(events).toEqual(["error"]);
  });
});
