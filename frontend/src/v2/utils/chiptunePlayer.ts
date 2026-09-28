import type { SoundtrackSink } from "@/stores/soundtrackPlayer";
import workletUrl from "./gmeAudioWorklet.js?worker&url";
import { type GmeCommand, type GmeReply, GmeRenderer } from "./gmeRenderer";

const GME_WASM_PATH = "/assets/gme/gme.wasm";

// Frames per main-thread render, about 85 ms at 48 kHz.
const SCRIPT_PROCESSOR_FRAMES = 4096;

/** Where the renderer runs: the port it listens on and the node it plays through. */
interface RendererHost {
  port: MessagePort;
  output: AudioNode;
}

let modulePromise: Promise<WebAssembly.Module> | null = null;

function compileGme(): Promise<WebAssembly.Module> {
  modulePromise ??= fetch(GME_WASM_PATH)
    .then((response) => {
      if (!response.ok) throw new Error(`gme.wasm: HTTP ${response.status}`);
      return response.arrayBuffer();
    })
    .then((bytes) => WebAssembly.compile(bytes))
    .catch((error) => {
      modulePromise = null;
      throw error;
    });
  return modulePromise;
}

/** Fetch a track, gunzipping VGZ and friends since libgme is built without zlib. */
async function fetchTrackData(url: string): Promise<ArrayBuffer> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  const data = await response.arrayBuffer();
  const head = new Uint8Array(data, 0, Math.min(2, data.byteLength));
  if (head[0] !== 0x1f || head[1] !== 0x8b) return data;
  const stream = new Blob([data])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
}

/** Plays console sound files through game-music-emu, with the `<audio>`
 * properties and events the mini player relies on. */
export class ChiptunePlayer extends EventTarget implements SoundtrackSink {
  private context: AudioContext | null = null;
  private gain: GainNode | null = null;
  private port: Promise<MessagePort> | null = null;
  // Held so the main-thread fallback's node isn't collected while it plays.
  private output: AudioNode | null = null;
  private loadToken = 0;
  private loaded = false;
  private isPaused = true;
  private position = 0;
  private length = 0;
  private level = 1;
  private silenced = false;

  get paused(): boolean {
    return this.isPaused;
  }

  get duration(): number {
    return this.length;
  }

  get currentTime(): number {
    return this.position;
  }

  set currentTime(seconds: number) {
    this.position = seconds;
    this.post({ type: "seek", ms: seconds * 1000 });
  }

  get volume(): number {
    return this.level;
  }

  set volume(value: number) {
    this.level = value;
    this.applyGain();
  }

  get muted(): boolean {
    return this.silenced;
  }

  set muted(value: boolean) {
    this.silenced = value;
    this.applyGain();
  }

  /**
   * Load one track of a sound file, replacing whatever was loaded.
   *
   * @param url Where to fetch the file from.
   * @param track Zero-based index of the song within the file.
   */
  async load(url: string, track = 0): Promise<void> {
    const token = this.reset();
    try {
      const [port, data] = await Promise.all([
        this.ensurePort(),
        fetchTrackData(url),
      ]);
      if (token !== this.loadToken) return;
      const command: GmeCommand = { type: "load", id: token, data, track };
      port.postMessage(command, [data]);
    } catch (error) {
      if (token !== this.loadToken) return;
      console.error("[chiptune] load failed", error);
      this.dispatchEvent(new Event("error"));
    }
  }

  async play(): Promise<void> {
    await this.ensurePort();
    await this.context?.resume();
    if (!this.isPaused) return;
    this.isPaused = false;
    if (this.loaded) this.post({ type: "play" });
    this.dispatchEvent(new Event("play"));
  }

  pause(): void {
    if (this.isPaused) return;
    this.isPaused = true;
    this.post({ type: "pause" });
    this.dispatchEvent(new Event("pause"));
  }

  /** Drop the loaded track without firing any events. */
  unload(): void {
    this.reset();
    this.post({ type: "unload" });
  }

  close(): void {
    this.unload();
    this.port = null;
    this.output = null;
    this.gain = null;
    void this.context?.close().catch(() => {});
    this.context = null;
  }

  private reset(): number {
    this.loaded = false;
    this.isPaused = true;
    this.position = 0;
    this.length = 0;
    return ++this.loadToken;
  }

  private applyGain() {
    if (this.gain) this.gain.gain.value = this.silenced ? 0 : this.level;
  }

  private post(message: GmeCommand) {
    if (!this.port) return;
    void this.port.then((port) => port.postMessage(message));
  }

  private ensurePort(): Promise<MessagePort> {
    this.port ??= this.createPort().catch((error) => {
      this.port = null;
      throw error;
    });
    return this.port;
  }

  private async createPort(): Promise<MessagePort> {
    const module = await compileGme();
    const context = (this.context ??= new AudioContext());
    // AudioWorklet only exists in secure contexts, and RomM is often served
    // over plain HTTP on a LAN address.
    const host = context.audioWorklet
      ? await hostInWorklet(context, module)
      : hostOnMainThread(context, module);
    const gain = context.createGain();
    host.output.connect(gain).connect(context.destination);
    this.output = host.output;
    this.gain = gain;
    this.applyGain();
    host.port.onmessage = (event: MessageEvent<GmeReply>) =>
      this.receive(event.data);
    return host.port;
  }

  private receive(message: GmeReply) {
    if (message.id !== this.loadToken) return;

    switch (message.type) {
      case "loaded":
        this.loaded = true;
        this.length = message.durationMs / 1000;
        this.dispatchEvent(new Event("loadedmetadata"));
        this.dispatchEvent(new Event("canplay"));
        if (!this.isPaused) this.post({ type: "play" });
        break;
      case "time":
        this.position = message.ms / 1000;
        this.dispatchEvent(new Event("timeupdate"));
        break;
      case "ended":
        this.isPaused = true;
        this.dispatchEvent(new Event("ended"));
        break;
      case "error":
        this.isPaused = true;
        this.dispatchEvent(new Event("error"));
        break;
    }
  }
}

async function hostInWorklet(
  context: AudioContext,
  module: WebAssembly.Module,
): Promise<RendererHost> {
  await context.audioWorklet.addModule(workletUrl);
  const node = new AudioWorkletNode(context, "gme-audio", {
    numberOfInputs: 0,
    numberOfOutputs: 1,
    outputChannelCount: [2],
    processorOptions: { module },
  });
  return { port: node.port, output: node };
}

function hostOnMainThread(
  context: AudioContext,
  module: WebAssembly.Module,
): RendererHost {
  const channel = new MessageChannel();
  const renderer = new GmeRenderer(module, context.sampleRate, (reply) =>
    channel.port2.postMessage(reply),
  );
  channel.port2.onmessage = (event: MessageEvent<GmeCommand>) =>
    renderer.handle(event.data);
  const node = context.createScriptProcessor(SCRIPT_PROCESSOR_FRAMES, 0, 2);
  node.onaudioprocess = (event) =>
    renderer.render(
      event.outputBuffer.getChannelData(0),
      event.outputBuffer.getChannelData(1),
    );
  return { port: channel.port1, output: node };
}
