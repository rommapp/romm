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

// Far above any real VGM, but stops a gzip bomb from exhausting the tab.
export const MAX_GUNZIPPED_BYTES = 64 * 1024 * 1024;

async function gunzip(data: ArrayBuffer): Promise<ArrayBuffer> {
  const reader = new Blob([data])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"))
    .getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_GUNZIPPED_BYTES) {
      await reader.cancel();
      throw new Error("gunzipped track is too large");
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out.buffer;
}

/** Fetch a track, gunzipping VGZ since libgme is built without zlib. */
async function fetchTrackData(
  url: string,
  signal: AbortSignal,
): Promise<ArrayBuffer> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  const data = await response.arrayBuffer();
  const head = new Uint8Array(data, 0, Math.min(2, data.byteLength));
  if (head[0] !== 0x1f || head[1] !== 0x8b) return data;
  return gunzip(data);
}

/** Plays console sound files through game-music-emu, with the `<audio>`
 * properties and events the mini player relies on. */
export class ChiptunePlayer extends EventTarget implements SoundtrackSink {
  private context: AudioContext | null = null;
  private gain: GainNode | null = null;
  private port: Promise<MessagePort> | null = null;
  // Held so the main-thread fallback's node isn't collected while it plays.
  private output: AudioNode | null = null;
  private download: AbortController | null = null;
  private loadToken = 0;
  // Bumped by every play, pause and load, so a play still starting up yields.
  private playToken = 0;
  private loaded = false;
  private failed = false;
  // Flips on each play or pause call, as `<audio>` does, so a quick second
  // press sees it. `started` is whether playback actually began.
  private isPaused = true;
  private started = false;
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

  // Reports the new position at once, as `<audio>` does, since a suspended
  // renderer only applies the seek when playback resumes.
  set currentTime(seconds: number) {
    this.position = seconds;
    // Before the file loads there is nothing to seek; "loaded" applies it.
    if (this.loaded) this.post({ type: "seek", ms: seconds * 1000 });
    this.dispatchEvent(new Event("timeupdate"));
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

  /** Load a sound file, replacing whatever was loaded. */
  async load(url: string): Promise<void> {
    // Silence the old track now, not once the new one has downloaded.
    this.unload();
    const token = this.loadToken;
    const download = new AbortController();
    this.download = download;
    try {
      const [port, data] = await Promise.all([
        this.ensurePort(),
        fetchTrackData(url, download.signal),
      ]);
      if (token !== this.loadToken) return;
      const command: GmeCommand = { type: "load", id: token, data };
      port.postMessage(command, [data]);
    } catch (error) {
      if (token !== this.loadToken) return;
      console.error("[chiptune] load failed", error);
      this.fail();
    }
  }

  async play(): Promise<void> {
    if (this.failed) return;
    const token = ++this.playToken;
    this.isPaused = false;
    try {
      await this.ensurePort();
      if (token !== this.playToken || this.failed) return;
      await this.context?.resume();
    } catch (error) {
      // Like a rejected `<audio>` play, a refused start leaves it paused.
      if (token === this.playToken) this.pause();
      throw error;
    }
    if (token !== this.playToken || this.failed || this.started) return;
    this.started = true;
    if (this.loaded) this.post({ type: "play" });
    this.dispatchEvent(new Event("play"));
    if (!this.loaded) this.dispatchEvent(new Event("waiting"));
  }

  pause(): void {
    this.playToken += 1;
    if (this.isPaused) return;
    this.isPaused = true;
    // A play still starting just yields; the renderer never started.
    if (this.started) {
      this.started = false;
      this.post({ type: "pause" });
    }
    this.suspendContext();
    this.dispatchEvent(new Event("pause"));
  }

  /** Drop the loaded track without firing any events. */
  unload(): void {
    this.download?.abort();
    this.download = null;
    this.playToken += 1;
    this.loadToken += 1;
    this.loaded = false;
    this.failed = false;
    this.isPaused = true;
    this.started = false;
    this.position = 0;
    this.length = 0;
    this.post({ type: "unload" });
    this.suspendContext();
  }

  close(): void {
    this.unload();
    this.port = null;
    this.output = null;
    this.gain = null;
    void this.context?.close().catch(() => {});
    this.context = null;
  }

  private fail() {
    this.failed = true;
    this.isPaused = true;
    this.started = false;
    this.suspendContext();
    this.dispatchEvent(new Event("error"));
  }

  // Stops the render callbacks and frees the output device; `play()` resumes.
  private suspendContext() {
    void this.context?.suspend().catch(() => {});
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
    // Created before the download, while the user's gesture still counts.
    const context = (this.context ??= new AudioContext());
    // A new context starts running; it stays suspended until `play()`.
    this.suspendContext();
    const module = await compileGme();
    const host = await hostRenderer(context, module, (output) =>
      this.crash(output),
    );
    const gain = context.createGain();
    host.output.connect(gain).connect(context.destination);
    this.output = host.output;
    this.gain = gain;
    this.applyGain();
    host.port.onmessage = (event: MessageEvent<GmeReply>) =>
      this.receive(event.data);
    return host.port;
  }

  // A processor that threw stays silent, so the next load builds a fresh one.
  private crash(output: AudioNode) {
    if (output !== this.output) return;
    console.error("[chiptune] renderer stopped");
    output.disconnect();
    this.gain?.disconnect();
    this.port = null;
    this.output = null;
    this.gain = null;
    this.fail();
  }

  private receive(message: GmeReply) {
    if (message.id !== this.loadToken) return;

    switch (message.type) {
      case "loaded":
        this.loaded = true;
        this.length = message.durationMs / 1000;
        if (this.position)
          this.post({ type: "seek", ms: this.position * 1000 });
        this.dispatchEvent(new Event("loadedmetadata"));
        this.dispatchEvent(new Event("canplay"));
        if (this.started) this.post({ type: "play" });
        break;
      case "time":
        this.position = message.ms / 1000;
        this.dispatchEvent(new Event("timeupdate"));
        break;
      case "ended":
        this.isPaused = true;
        this.started = false;
        this.suspendContext();
        this.dispatchEvent(new Event("ended"));
        break;
      case "error":
        this.fail();
        break;
    }
  }
}

/**
 * Args:
 *   onCrash: called when the worklet's processor throws, e.g. on a libgme trap.
 */
async function hostRenderer(
  context: AudioContext,
  module: WebAssembly.Module,
  onCrash: (output: AudioNode) => void,
): Promise<RendererHost> {
  // AudioWorklet only exists in secure contexts, and self-hosted instances are
  // often served over plain HTTP on a LAN address.
  if (!context.audioWorklet) return hostOnMainThread(context, module);
  try {
    return await hostInWorklet(context, module, onCrash);
  } catch (error) {
    // Some engines refuse the worklet or the compiled module handed to it.
    console.error(
      "[chiptune] AudioWorklet failed, rendering on the main thread",
      error,
    );
    return hostOnMainThread(context, module);
  }
}

async function hostInWorklet(
  context: AudioContext,
  module: WebAssembly.Module,
  onCrash: (output: AudioNode) => void,
): Promise<RendererHost> {
  await context.audioWorklet.addModule(workletUrl);
  const node = new AudioWorkletNode(context, "gme-audio", {
    numberOfInputs: 0,
    numberOfOutputs: 1,
    outputChannelCount: [2],
    processorOptions: { module },
  });
  node.onprocessorerror = () => onCrash(node);
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
