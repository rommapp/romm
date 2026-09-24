import workletUrl from "./pico8AudioWorklet.js?url";

const GAIN = 0.75;

export interface Pico8AudioOptions {
  sampleRate: number;
  /** Samples one emulated frame can produce, which sizes the pooled buffers. */
  samplesPerFrame: number;
}

export interface Pico8Audio {
  /**
   * Hand a pooled buffer to `fill` and forward however many samples it wrote.
   *
   * @param fill Writes samples into the buffer and returns the count.
   */
  pump: (fill: (target: Int16Array) => number) => void;
  close: () => void;
}

function openContext(sampleRate: number): AudioContext | null {
  try {
    return new AudioContext({ sampleRate });
  } catch {
    // Firefox rejects a rate the device cannot run at; its own is fine, since
    // the worklet is resampled by the graph either way.
    try {
      return new AudioContext();
    } catch {
      return null;
    }
  }
}

/**
 * Open the PICO-8 audio graph: one worklet node fed from a buffer pool.
 *
 * @param options The runtime's sample rate and per-frame sample budget.
 * @returns The sink, or null when Web Audio is unavailable.
 */
export async function createPico8Audio(
  options: Pico8AudioOptions,
): Promise<Pico8Audio | null> {
  const context = openContext(options.sampleRate);
  if (!context) return null;

  let node: AudioWorkletNode;
  try {
    await context.audioWorklet.addModule(workletUrl);
    node = new AudioWorkletNode(context, "pico8-audio", {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
  } catch (error) {
    void context.close().catch(() => {});
    throw error;
  }

  const gain = context.createGain();
  gain.gain.value = GAIN;
  node.connect(gain).connect(context.destination);
  void context.resume().catch(() => {});

  // Two buffers cover a frame in flight plus the one being refilled.
  const pool: Int16Array[] = [
    new Int16Array(options.samplesPerFrame),
    new Int16Array(options.samplesPerFrame),
  ];
  // The worklet returns a view sized to what it read, so re-wrap the whole
  // buffer to keep every pooled entry a full frame long.
  node.port.onmessage = (event: MessageEvent<Int16Array>) => {
    pool.push(new Int16Array(event.data.buffer));
  };

  let closed = false;

  return {
    pump(fill) {
      if (closed) return;
      const target = pool.pop() ?? new Int16Array(options.samplesPerFrame);
      const written = fill(target);
      if (written <= 0) {
        pool.push(target);
        return;
      }
      const chunk =
        written === target.length ? target : target.subarray(0, written);
      node.port.postMessage(chunk, [target.buffer]);
    },
    close() {
      if (closed) return;
      closed = true;
      node.port.onmessage = null;
      node.disconnect();
      gain.disconnect();
      void context.close().catch(() => {});
    },
  };
}
