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

type Posted = {
  type: string;
  id?: number;
  data?: ArrayBuffer;
  ms?: number;
};

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

const SPC_BYTES = new TextEncoder().encode("SNES-SPC700 Sound File Data");

let port: FakePort;
const addModule = vi.fn(async () => {});
const resume = vi.fn(async () => {});
const suspend = vi.fn(async () => {});
const gain = { gain: { value: -1 }, connect: vi.fn() };
let bodies: Map<string, Uint8Array>;

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function loaded(player: ChiptunePlayer, durationMs = 158000) {
  await player.load("/track.spc");
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
    ["/track.spc", SPC_BYTES],
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
  stubContext();
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
    expect(new Uint8Array(load?.data ?? new ArrayBuffer(0))).toEqual(SPC_BYTES);
    expect(player.duration).toBe(158);
    expect(events).toEqual(["loadedmetadata", "canplay"]);
  });

  it("gunzips a VGZ file before handing it over", async () => {
    bodies.set("/track.spc", new Uint8Array(gzipSync(SPC_BYTES)));
    const player = new ChiptunePlayer();

    await player.load("/track.spc");

    const data = port.lastLoad()?.data ?? new ArrayBuffer(0);
    expect(new Uint8Array(data)).toEqual(SPC_BYTES);
  });

  it("starts the worklet only once a play asked for early has a track", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    const loading = player.load("/track.spc");
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

    await player.load("/track.spc");

    expect(port.types()).toEqual(["unload", "load"]);
  });

  it("stops reporting paused as soon as play is called, like <audio>", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);
    const events = recordEvents(player);

    const starting = player.play();
    expect(player.paused).toBe(false);
    await starting;

    expect(events).toEqual(["play"]);
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

  it("leaves a new context suspended when its first play is cancelled", async () => {
    const player = new ChiptunePlayer();

    const loading = player.load("/track.spc");
    const starting = player.play();
    player.unload();
    await Promise.all([loading, starting]);

    expect(suspend).toHaveBeenCalled();
    expect(resume).not.toHaveBeenCalled();
  });

  it("won't play a track that failed to load", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/missing.spc");
    await player.play();

    expect(events).toEqual(["error"]);
    expect(player.paused).toBe(true);
  });

  it("drops replies about a track that was replaced", async () => {
    const player = new ChiptunePlayer();
    const staleId = await loaded(player);
    const events = recordEvents(player);

    await player.load("/track.spc");
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

  it("forwards seeks to the renderer and reports the new position", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);

    const events = recordEvents(player);
    player.currentTime = 42;
    await flush();

    expect(events).toEqual(["timeupdate"]);
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

    await player.load("/missing.spc");

    expect(events).toEqual(["error"]);
  });

  it("fires error when the worklet rejects the file", async () => {
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/track.spc");
    port.reply({ type: "error", id: port.lastLoad()?.id });

    expect(events).toEqual(["error"]);
  });

  it("suspends the audio context whenever nothing plays", async () => {
    const player = new ChiptunePlayer();
    await loaded(player);
    await player.play();
    suspend.mockClear();

    player.pause();
    expect(suspend).toHaveBeenCalledTimes(1);

    await player.play();
    player.unload();
    expect(suspend).toHaveBeenCalledTimes(2);
    expect(resume).toHaveBeenCalled();
  });

  it("renders on the main thread where AudioWorklet is unavailable", async () => {
    const processor = stubContext({ worklet: false });
    const player = new ChiptunePlayer();
    const events = recordEvents(player);

    await player.load("/track.spc");
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
    vi.spyOn(console, "error").mockImplementation(() => {});
    addModule.mockRejectedValueOnce(new Error("DataCloneError"));
    const player = new ChiptunePlayer();

    await player.load("/track.spc");
    await flush();

    expect(addModule).toHaveBeenCalled();
    expect(renderer.commands.at(-1)?.type).toBe("load");
  });
});

/** An AudioContext, with or without AudioWorklet, returning its ScriptProcessorNode. */
function stubContext({ worklet = true } = {}) {
  const processor = {
    onaudioprocess: null as ((event: object) => void) | null,
    connect: vi.fn(() => gain),
  };
  vi.stubGlobal(
    "AudioContext",
    class {
      audioWorklet = worklet ? { addModule } : undefined;
      sampleRate = 48000;
      destination = {};
      resume = resume;
      suspend = suspend;
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
