import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPico8Audio } from "./pico8Audio";

vi.mock("./pico8AudioWorklet.js?url", () => ({ default: "/worklet.js" }));

const addModule = vi.fn(async () => {});
const posted: { chunk: Int16Array; transfer: Transferable[] }[] = [];

class FakePort {
  onmessage: ((event: MessageEvent<Int16Array>) => void) | null = null;

  postMessage(chunk: Int16Array, transfer: Transferable[]) {
    posted.push({ chunk, transfer });
  }

  /** Stand in for the worklet handing the storage back. */
  recycle(buffer: ArrayBufferLike) {
    this.onmessage?.({
      data: new Int16Array(buffer),
    } as MessageEvent<Int16Array>);
  }
}

const port = new FakePort();
const nodeConnect = vi.fn();
const nodeDisconnect = vi.fn();
const gainDisconnect = vi.fn();
const contextClose = vi.fn(async () => {});
const gain = {
  gain: { value: 0 },
  connect: vi.fn(),
  disconnect: gainDisconnect,
};

let sampleRateAsked: number | undefined;
let contextThrows = false;

beforeEach(() => {
  posted.length = 0;
  vi.clearAllMocks();
  contextThrows = false;
  sampleRateAsked = undefined;
  port.onmessage = null;

  vi.stubGlobal(
    "AudioContext",
    class {
      audioWorklet = { addModule };
      destination = {};
      constructor(options?: { sampleRate?: number }) {
        if (contextThrows) throw new Error("bad sample rate");
        sampleRateAsked = options?.sampleRate;
      }
      createGain() {
        return gain;
      }
      close = contextClose;
      resume = vi.fn(async () => {});
    },
  );
  vi.stubGlobal(
    "AudioWorkletNode",
    class {
      port = port;
      connect = nodeConnect.mockReturnValue(gain);
      disconnect = nodeDisconnect;
    },
  );
  // node.connect(gain).connect(destination)
  gain.connect.mockReturnValue(gain);
});

const open = () =>
  createPico8Audio({ sampleRate: 22050, samplesPerFrame: 735 });

describe("createPico8Audio", () => {
  it("opens the graph at the runtime's sample rate", async () => {
    const audio = await open();

    expect(audio).not.toBeNull();
    expect(sampleRateAsked).toBe(22050);
    expect(addModule).toHaveBeenCalledWith("/worklet.js");
    expect(gain.gain.value).toBeCloseTo(0.75);
  });

  it("falls back to the device rate when the asked-for one is refused", async () => {
    let first = true;
    vi.stubGlobal(
      "AudioContext",
      class {
        audioWorklet = { addModule };
        destination = {};
        constructor(options?: { sampleRate?: number }) {
          if (first) {
            first = false;
            throw new Error("bad sample rate");
          }
          sampleRateAsked = options?.sampleRate;
        }
        createGain() {
          return gain;
        }
        close = contextClose;
        resume = vi.fn(async () => {});
      },
    );

    expect(await open()).not.toBeNull();
    expect(sampleRateAsked).toBeUndefined();
  });

  it("returns null when Web Audio is missing entirely", async () => {
    contextThrows = true;
    expect(await open()).toBeNull();
  });

  it("closes the context when the worklet module fails to load", async () => {
    addModule.mockRejectedValueOnce(new Error("blocked"));

    await expect(open()).rejects.toThrow("blocked");
    expect(contextClose).toHaveBeenCalled();
  });

  it("forwards only the samples the runtime wrote, transferring the buffer", async () => {
    const audio = await open();

    audio?.pump((target) => {
      target[0] = 100;
      target[1] = -100;
      return 2;
    });

    expect(posted).toHaveLength(1);
    expect([...posted[0].chunk]).toEqual([100, -100]);
    expect(posted[0].transfer).toHaveLength(1);
  });

  it("posts nothing for a silent frame", async () => {
    const audio = await open();

    audio?.pump(() => 0);

    expect(posted).toHaveLength(0);
  });

  it("reuses recycled storage instead of allocating per frame", async () => {
    const audio = await open();

    // Drain the two pooled buffers, then hand one back.
    audio?.pump(() => 1);
    audio?.pump(() => 1);
    const returned = new ArrayBuffer(735 * 2);
    port.recycle(returned);
    audio?.pump(() => 1);

    expect(posted[2].chunk.buffer).toBe(returned);
  });

  it("recycles a full-length view even when the worklet returns a short one", async () => {
    const audio = await open();
    const buffer = new ArrayBuffer(735 * 2);

    // The worklet reads 2 samples and hands back a 2-long view of the buffer.
    port.onmessage?.({
      data: new Int16Array(buffer, 0, 2),
    } as MessageEvent<Int16Array>);
    audio?.pump((target) => target.length);

    expect(posted[0].chunk).toHaveLength(735);
  });

  it("stops forwarding once closed", async () => {
    const audio = await open();
    audio?.close();

    audio?.pump(() => 1);

    expect(posted).toHaveLength(0);
    expect(nodeDisconnect).toHaveBeenCalled();
    expect(gainDisconnect).toHaveBeenCalled();
    expect(contextClose).toHaveBeenCalled();
  });
});
