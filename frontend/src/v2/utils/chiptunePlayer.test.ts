import { gzipSync } from "node:zlib";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChiptunePlayer } from "./chiptunePlayer";

vi.mock("./gmeAudioWorklet.js?worker&url", () => ({ default: "/worklet.js" }));

// Stands in for libgme when the player falls back to the main thread.
const renderer = vi.hoisted(() => ({
  commands: [] as { type: string }[],
  rendered: 0,
  send: null as ((reply: object) => void) | null,
}));
vi.mock("./gmeRenderer", () => ({
  GmeRenderer: class {
    constructor(_module: unknown, _rate: number, send: (r: object) => void) {
      renderer.send = send;
    }
    handle(command: { type: string }) {
      renderer.commands.push(command);
    }
    render() {
      renderer.rendered += 1;
    }
  },
}));

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
    "waiting",
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
  renderer.commands = [];
  renderer.rendered = 0;
  renderer.send = null;
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
    expect(events).toEqual(["play", "waiting"]);
    expect(port.types()).not.toContain("play");

    port.reply({ type: "loaded", id: port.lastLoad()?.id, durationMs: 1000 });
    await flush();

    expect(player.paused).toBe(false);
    expect(port.types()).toContain("play");
  });

  it("silences the previous track while the next one downloads", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);
    port.posted = [];

    await player.load("/track.nsf");

    expect(port.types()).toEqual(["unload", "load"]);
  });

  it("stays paused when a pause overtakes a play still starting", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);
    const events = recordEvents(player);

    const starting = player.play();
    player.pause();
    await starting;

    expect(player.paused).toBe(true);
    expect(events).toEqual([]);
    expect(port.types()).not.toContain("play");
  });

  it("won't play a track that failed to load", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/missing.nsf");
    await player.play();

    expect(events).toEqual(["error"]);
    expect(player.paused).toBe(true);
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

  it("renders on the main thread where AudioWorklet is unavailable", async () => {
    const processor = stubMainThreadContext(undefined);
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/track.nsf");
    await flush();
    const load = renderer.commands.at(-1) as { type: string; id: number };
    expect(load.type).toBe("load");
    expect(addModule).not.toHaveBeenCalled();

    renderer.send?.({ type: "loaded", id: load.id, durationMs: 2000 });
    await flush();
    const channel = { getChannelData: () => new Float32Array(4) };
    processor.onaudioprocess?.({ outputBuffer: channel });

    expect(events).toEqual(["loadedmetadata", "canplay"]);
    expect(player.duration).toBe(2);
    expect(renderer.rendered).toBe(1);
  });

  it("falls back to the main thread when the worklet won't start", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    addModule.mockRejectedValueOnce(new Error("DataCloneError"));
    stubMainThreadContext({ addModule });
    const player = new ChiptunePlayer();

    await player.load("/track.nsf");
    await flush();

    expect(addModule).toHaveBeenCalled();
    expect(renderer.commands.at(-1)?.type).toBe("load");
  });
});

/** An AudioContext that renders through a ScriptProcessorNode. */
function stubMainThreadContext(
  audioWorklet: { addModule: () => unknown } | undefined,
) {
  const processor = {
    onaudioprocess: null as ((event: object) => void) | null,
    connect: vi.fn(() => gain),
  };
  vi.stubGlobal(
    "AudioContext",
    class {
      audioWorklet = audioWorklet;
      sampleRate = 48000;
      destination = {};
      resume = resume;
      close = vi.fn(async () => {});
      createGain() {
        return gain;
      }
      createScriptProcessor() {
        return processor;
      }
    },
  );
  return processor;
}
