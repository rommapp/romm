// Runs game-music-emu on the audio thread, rendering each quantum on demand, so
// playback survives a busy main thread and a background tab.
import { GmeRenderer } from "./gmeRenderer";

class GmeProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.renderer = new GmeRenderer(
      options.processorOptions.module,
      sampleRate,
      (reply) => this.port.postMessage(reply),
    );
    this.port.onmessage = (event) => this.renderer.handle(event.data);
  }

  process(_inputs, outputs) {
    const [left, right] = outputs[0];
    if (left) this.renderer.render(left, right);
    return true;
  }
}

registerProcessor("gme-audio", GmeProcessor);
