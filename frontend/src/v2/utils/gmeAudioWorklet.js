// Runs game-music-emu on the audio thread, rendering each quantum on demand, so
// playback survives a busy main thread and a background tab.

const IMPORTS = { env: { emscripten_notify_memory_growth() {} } };

// About four position reports a second, matching `<audio>` timeupdate.
const TIME_REPORT_INTERVAL_SECONDS = 0.25;

class GmeProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { exports } = new WebAssembly.Instance(
      options.processorOptions.module,
      IMPORTS,
    );
    exports._initialize();
    this.gme = exports;
    this.emu = 0;
    // Echoed on every reply, so the page can drop those about a replaced track.
    this.loadId = 0;
    this.playing = false;
    this.bufferPointer = 0;
    this.bufferSamples = 0;
    this.quantaPerReport = Math.max(
      1,
      Math.round((sampleRate * TIME_REPORT_INTERVAL_SECONDS) / 128),
    );
    this.quantaSinceReport = 0;
    this.port.onmessage = (event) => this.handle(event.data);
  }

  handle(message) {
    switch (message.type) {
      case "load":
        this.load(message.id, message.data, message.track);
        break;
      case "play":
        this.playing = this.emu !== 0;
        break;
      case "pause":
        this.playing = false;
        break;
      case "seek":
        if (this.emu) {
          this.gme.gme_seek(this.emu, Math.max(0, Math.round(message.ms)));
          this.reportTime();
        }
        break;
      case "unload":
        this.unload();
        break;
    }
  }

  load(id, data, track) {
    this.unload();
    this.loadId = id;
    const bytes = new Uint8Array(data);
    const pointer = this.gme.malloc(bytes.length);
    new Uint8Array(this.gme.memory.buffer, pointer, bytes.length).set(bytes);
    // libgme copies the file into its own buffer, so ours is freed at once.
    const emu = this.gme.romm_gme_open(pointer, bytes.length, sampleRate);
    this.gme.free(pointer);

    const durationMs = emu ? this.gme.romm_gme_start(emu, track) : -1;
    if (durationMs < 0) {
      if (emu) this.gme.gme_delete(emu);
      this.send({ type: "error" });
      return;
    }
    this.emu = emu;
    this.send({ type: "loaded", durationMs });
  }

  send(message) {
    this.port.postMessage({ ...message, id: this.loadId });
  }

  unload() {
    this.playing = false;
    if (this.emu) this.gme.gme_delete(this.emu);
    this.emu = 0;
  }

  reportTime() {
    this.quantaSinceReport = 0;
    this.send({ type: "time", ms: this.gme.gme_tell(this.emu) });
  }

  // Interleaved stereo samples, reallocated only when the quantum grows.
  reserve(count) {
    if (count <= this.bufferSamples) return;
    if (this.bufferPointer) this.gme.free(this.bufferPointer);
    this.bufferPointer = this.gme.malloc(count * 2);
    this.bufferSamples = count;
  }

  process(_inputs, outputs) {
    const [left, right] = outputs[0];
    if (!this.playing || !left) return true;

    const frames = left.length;
    this.reserve(frames * 2);
    if (this.gme.gme_play(this.emu, frames * 2, this.bufferPointer)) {
      this.unload();
      this.send({ type: "error" });
      return true;
    }
    // Memory growth detaches old views, so take a fresh one each quantum.
    const pcm = new Int16Array(
      this.gme.memory.buffer,
      this.bufferPointer,
      frames * 2,
    );
    for (let frame = 0; frame < frames; frame += 1) {
      left[frame] = pcm[frame * 2] / 32768;
      if (right) right[frame] = pcm[frame * 2 + 1] / 32768;
    }

    if (this.gme.gme_track_ended(this.emu)) {
      this.playing = false;
      this.reportTime();
      this.send({ type: "ended" });
    } else if (++this.quantaSinceReport >= this.quantaPerReport) {
      this.reportTime();
    }
    return true;
  }
}

registerProcessor("gme-audio", GmeProcessor);
