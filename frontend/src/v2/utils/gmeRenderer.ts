// Drives game-music-emu one render quantum at a time. Hosted by the AudioWorklet
// where the browser has one, else by a ScriptProcessorNode on the main thread.

const IMPORTS = { env: { emscripten_notify_memory_growth() {} } };

// About four position reports a second, matching `<audio>` timeupdate.
const TIME_REPORT_INTERVAL_SECONDS = 0.25;

type GmeReplyBody =
  | { type: "loaded"; durationMs: number }
  | { type: "time"; ms: number }
  | { type: "ended" }
  | { type: "error" };

/** The renderer's replies, each tagged with the load it answers. */
export type GmeReply = { id: number } & GmeReplyBody;

export type GmeCommand =
  | { type: "load"; id: number; data: ArrayBuffer }
  | { type: "play" }
  | { type: "pause" }
  | { type: "seek"; ms: number }
  | { type: "unload" };

type GmeExports = {
  memory: WebAssembly.Memory;
  _initialize: () => void;
  malloc: (size: number) => number;
  free: (pointer: number) => void;
  romm_gme_open: (data: number, size: number, sampleRate: number) => number;
  romm_gme_start: (emu: number) => number;
  gme_play: (emu: number, count: number, out: number) => number;
  gme_seek: (emu: number, ms: number) => number;
  gme_tell: (emu: number) => number;
  gme_track_ended: (emu: number) => number;
  gme_delete: (emu: number) => void;
};

const GME_FUNCTIONS = [
  "_initialize",
  "malloc",
  "free",
  "romm_gme_open",
  "romm_gme_start",
  "gme_play",
  "gme_seek",
  "gme_tell",
  "gme_track_ended",
  "gme_delete",
] as const;

function gmeExports(exports: WebAssembly.Exports): GmeExports {
  const missing = GME_FUNCTIONS.filter(
    (name) => typeof exports[name] !== "function",
  );
  if (!(exports.memory instanceof WebAssembly.Memory) || missing.length) {
    throw new Error(`gme.wasm is missing exports: ${missing.join(", ")}`);
  }
  return exports as GmeExports;
}

export class GmeRenderer {
  private gme: GmeExports;
  private emu = 0;
  // Echoed on every reply, so the page can drop those about a replaced track.
  private loadId = 0;
  private playing = false;
  // A scrub's seeks collapse into one per quantum, since each emulates its way
  // to the target.
  private pendingSeekMs: number | null = null;
  private bufferPointer = 0;
  private bufferSamples = 0;
  private pcm = new Int16Array(0);
  private framesSinceReport = 0;
  private readonly framesPerReport: number;
  private readonly sampleRate: number;
  private readonly send: (reply: GmeReply) => void;

  /**
   * Instantiate gme.wasm for one output.
   *
   * Args:
   *   module: the compiled gme.wasm.
   *   sampleRate: the output rate libgme renders at.
   *   send: delivers replies to the ChiptunePlayer.
   */
  constructor(
    module: WebAssembly.Module,
    sampleRate: number,
    send: (reply: GmeReply) => void,
  ) {
    this.sampleRate = sampleRate;
    this.send = send;
    this.gme = gmeExports(new WebAssembly.Instance(module, IMPORTS).exports);
    this.gme._initialize();
    this.framesPerReport = sampleRate * TIME_REPORT_INTERVAL_SECONDS;
  }

  handle(command: GmeCommand) {
    switch (command.type) {
      case "load":
        this.load(command.id, command.data);
        break;
      case "play":
        // Like `<audio>`, playing an ended track starts it over.
        if (this.emu && this.gme.gme_track_ended(this.emu) && this.restart()) {
          this.reportTime();
        }
        this.playing = this.emu !== 0;
        break;
      case "pause":
        this.playing = false;
        break;
      case "seek":
        if (this.emu) this.pendingSeekMs = command.ms;
        break;
      case "unload":
        this.unload();
        break;
    }
  }

  /** Fill one quantum of output, or silence while nothing plays. */
  render(left: Float32Array, right: Float32Array) {
    if (this.pendingSeekMs !== null) {
      const ms = this.pendingSeekMs;
      this.pendingSeekMs = null;
      this.seek(ms);
    }
    const frames = left.length;
    if (this.playing) {
      this.reserve(frames * 2);
      if (this.gme.gme_play(this.emu, frames * 2, this.bufferPointer)) {
        this.unload();
        this.reply({ type: "error" });
      }
    }
    if (!this.playing) {
      left.fill(0);
      right.fill(0);
      return;
    }

    const pcm = this.pcmView(frames * 2);
    for (let frame = 0; frame < frames; frame += 1) {
      left[frame] = pcm[frame * 2]! / 32768;
      right[frame] = pcm[frame * 2 + 1]! / 32768;
    }

    if (this.gme.gme_track_ended(this.emu)) {
      this.playing = false;
      this.reportTime();
      this.reply({ type: "ended" });
    } else {
      this.framesSinceReport += frames;
      if (this.framesSinceReport >= this.framesPerReport) this.reportTime();
    }
  }

  private load(id: number, data: ArrayBuffer) {
    this.unload();
    this.loadId = id;
    const emu = this.open(data);
    const durationMs = emu ? this.gme.romm_gme_start(emu) : -1;
    if (durationMs < 0) {
      if (emu) this.gme.gme_delete(emu);
      this.reply({ type: "error" });
      return;
    }
    this.emu = emu;
    this.reply({ type: "loaded", durationMs });
  }

  /** Open a file from a copy in wasm memory; libgme keeps its own copy. */
  private open(data: ArrayBuffer): number {
    const bytes = new Uint8Array(data);
    const pointer = this.gme.malloc(bytes.length);
    new Uint8Array(this.gme.memory.buffer, pointer, bytes.length).set(bytes);
    try {
      return this.gme.romm_gme_open(pointer, bytes.length, this.sampleRate);
    } finally {
      this.gme.free(pointer);
    }
  }

  private seek(ms: number) {
    const target = Math.max(0, Math.round(ms));
    // libgme seeks backwards by restarting the track, which drops its fade.
    if (target < this.gme.gme_tell(this.emu) && !this.restart()) return;
    this.gme.gme_seek(this.emu, target);
    this.reportTime();
  }

  /** Start the track over with its fade, or unload it if libgme refuses. */
  private restart(): boolean {
    if (this.gme.romm_gme_start(this.emu) >= 0) return true;
    this.unload();
    this.reply({ type: "error" });
    return false;
  }

  private reply(message: GmeReplyBody) {
    this.send({ ...message, id: this.loadId });
  }

  private unload() {
    this.playing = false;
    this.pendingSeekMs = null;
    if (this.emu) this.gme.gme_delete(this.emu);
    this.emu = 0;
  }

  private reportTime() {
    this.framesSinceReport = 0;
    this.reply({ type: "time", ms: this.gme.gme_tell(this.emu) });
  }

  // Memory growth detaches old views, so the view is rebuilt when that happens.
  private pcmView(count: number): Int16Array {
    const { buffer } = this.gme.memory;
    if (
      this.pcm.buffer !== buffer ||
      this.pcm.byteOffset !== this.bufferPointer ||
      this.pcm.length !== count
    ) {
      this.pcm = new Int16Array(buffer, this.bufferPointer, count);
    }
    return this.pcm;
  }

  // Interleaved stereo samples, reallocated only when the quantum grows.
  private reserve(count: number) {
    if (count <= this.bufferSamples) return;
    if (this.bufferPointer) this.gme.free(this.bufferPointer);
    this.bufferPointer = this.gme.malloc(count * 2);
    this.bufferSamples = count;
  }
}
