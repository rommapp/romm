// Audio sink for the PICO-8 player, running on the audio thread so playback
// survives a stalled main thread. The player posts Int16 frames in; this
// buffers them and drains one render quantum at a time.
//
// The player route gets no COOP/COEP, so SharedArrayBuffer is unavailable and
// samples arrive by transfer. Each buffer is transferred straight back once
// copied, so steady-state playback allocates nothing on either thread.

// Roughly a quarter second at PICO-8's rate, so a late frame does not
// underrun while a long stall still drops rather than drifting.
const RING_CAPACITY = 8192;

class Pico8AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ring = new Float32Array(RING_CAPACITY);
    this.read = 0;
    this.available = 0;
    this.port.onmessage = (event) => this.enqueue(event.data);
  }

  enqueue(samples) {
    const count = Math.min(samples.length, RING_CAPACITY - this.available);
    let write = (this.read + this.available) % RING_CAPACITY;
    for (let index = 0; index < count; index += 1) {
      this.ring[write] = samples[index] / 32768;
      write = write + 1 === RING_CAPACITY ? 0 : write + 1;
    }
    this.available += count;
    // Hand the storage back for the player to refill.
    this.port.postMessage(samples, [samples.buffer]);
  }

  process(_inputs, outputs) {
    const channel = outputs[0][0];
    if (!channel) return true;

    const drained = Math.min(channel.length, this.available);
    for (let index = 0; index < drained; index += 1) {
      channel[index] = this.ring[this.read];
      this.read = this.read + 1 === RING_CAPACITY ? 0 : this.read + 1;
    }
    this.available -= drained;
    // An underrun outputs silence rather than repeating the last block, which
    // would ring audibly on a cart that pauses.
    channel.fill(0, drained);
    return true;
  }
}

registerProcessor("pico8-audio", Pico8AudioProcessor);
