import { loadScript } from "./scriptLoader";

export const PICO8_WIDTH = 128;
export const PICO8_HEIGHT = 128;
export const PICO8_FRAME_RATE = 30;

export const PICO8_INPUT_BITS = {
  left: 0x01,
  right: 0x02,
  up: 0x04,
  down: 0x08,
  a: 0x10,
  b: 0x20,
} as const;

const PICO8_WASM_PATH = "/assets/pico8/fake08.wasm";
const PICO8_SCRIPT_PATH = "/assets/pico8/fake08.js";
const FRAMEBUFFER_BYTES = (PICO8_WIDTH * PICO8_HEIGHT) / 2;
const PALETTE_BYTES = 16 * 4;

export interface Fake08Module {
  HEAPU8: Uint8Array;
  _f08_init: () => void;
  _f08_load_cart_data: (pointer: number, length: number) => number;
  _f08_step_frame: () => void;
  _f08_get_framebuffer_ptr: () => number;
  _f08_get_palette_rgba: (pointer: number) => void;
  _f08_get_target_fps: () => number;
  _f08_get_last_error: () => number;
  _f08_set_inputs: (
    keyDown: number,
    keyHeld: number,
    mouseX: number,
    mouseY: number,
    mouseButtons: number,
  ) => void;
  _f08_fill_audio_buffer: (pointer: number, maxSamples: number) => number;
  _f08_get_audio_sample_rate: () => number;
  _malloc: (size: number) => number;
  _free: (pointer: number) => void;
  UTF8ToString: (pointer: number) => string;
}

type Fake08Factory = (options: {
  locateFile: (path: string) => string;
}) => Promise<Fake08Module>;

declare global {
  interface Window {
    Fake08Module?: Fake08Factory;
  }
}

let scriptPromise: Promise<void> | null = null;

function loadPico8Script(): Promise<void> {
  if (window.Fake08Module) return Promise.resolve();
  scriptPromise ??= loadScript(PICO8_SCRIPT_PATH).catch((error) => {
    scriptPromise = null;
    throw error;
  });
  return scriptPromise;
}

// Builds with ABORTING_MALLOC disabled return 0 instead of trapping, and
// writing through a null pointer would silently corrupt the heap.
function allocate(module: Fake08Module, bytes: number): number {
  const pointer = module._malloc(bytes);
  if (!pointer) throw new Error("PICO-8 ran out of memory");
  return pointer;
}

function lastRuntimeError(module: Fake08Module): string | null {
  const pointer = module._f08_get_last_error();
  if (!pointer) return null;
  const message = module.UTF8ToString(pointer);
  module._free(pointer);
  return message || null;
}

export interface Pico8Input {
  keyDown: number;
  keyHeld: number;
  mouseX: number;
  mouseY: number;
  mouseButtons: number;
}

export interface Pico8Runtime {
  readonly frameRate: number;
  readonly audioSampleRate: number;
  /** Samples a single frame can produce, for sizing the caller's buffer. */
  readonly samplesPerFrame: number;
  loadCart: (bytes: Uint8Array) => void;
  advance: (input: Pico8Input) => void;
  render: () => void;
  /**
   * Copy this frame's audio into the caller's buffer.
   *
   * @param target Destination, at least `samplesPerFrame` long.
   * @returns How many samples were written.
   */
  readAudio: (target: Int16Array) => number;
  dispose: () => void;
}

export async function createPico8Runtime(
  canvas: HTMLCanvasElement,
): Promise<Pico8Runtime> {
  await loadPico8Script();
  const factory = window.Fake08Module;
  if (!factory) throw new Error("PICO-8 runtime is unavailable");

  const module = await factory({
    locateFile: (path) => (path.endsWith(".wasm") ? PICO8_WASM_PATH : path),
  });
  const canvasContext = canvas.getContext("2d", { alpha: false });
  if (!canvasContext) throw new Error("PICO-8 needs a 2D canvas");
  const context = canvasContext;

  canvas.width = PICO8_WIDTH;
  canvas.height = PICO8_HEIGHT;
  module._f08_init();

  const framebufferPointer = module._f08_get_framebuffer_ptr();
  if (!framebufferPointer) throw new Error("PICO-8 framebuffer is unavailable");

  const palettePointer = allocate(module, PALETTE_BYTES);
  const samplesPerFrame = Math.ceil(
    module._f08_get_audio_sample_rate() / PICO8_FRAME_RATE,
  );
  let audioPointer: number;
  try {
    audioPointer = allocate(module, samplesPerFrame * 2);
  } catch (error) {
    module._free(palettePointer);
    throw error;
  }
  const imageData = context.createImageData(PICO8_WIDTH, PICO8_HEIGHT);
  const pixels = new Uint32Array(imageData.data.buffer);

  // Packed-RGBA lookup for the 16 palette entries, written through an aliased
  // byte view so the word order is right on either endianness.
  const paletteLutBytes = new Uint8Array(PALETTE_BYTES);
  const paletteLut = new Uint32Array(paletteLutBytes.buffer);

  let heapBuffer: ArrayBufferLike | null = null;
  let palette: Uint8Array<ArrayBufferLike> = new Uint8Array(0);
  let framebuffer: Uint8Array<ArrayBufferLike> = new Uint8Array(0);
  let disposed = false;

  // Heap growth detaches existing views, so rebind whenever the buffer changes.
  function syncHeapViews() {
    if (heapBuffer === module.HEAPU8.buffer) return;
    heapBuffer = module.HEAPU8.buffer;
    palette = new Uint8Array(heapBuffer, palettePointer, PALETTE_BYTES);
    framebuffer = new Uint8Array(
      heapBuffer,
      framebufferPointer,
      FRAMEBUFFER_BYTES,
    );
  }

  function render() {
    if (disposed) return;
    module._f08_get_palette_rgba(palettePointer);
    syncHeapViews();

    // Carts remap the palette at runtime, so the lookup is rebuilt per paint.
    paletteLutBytes.set(palette);
    for (let alpha = 3; alpha < PALETTE_BYTES; alpha += 4) {
      paletteLutBytes[alpha] = 0xff;
    }

    let target = 0;
    for (let index = 0; index < FRAMEBUFFER_BYTES; index += 1) {
      const packed = framebuffer[index];
      pixels[target] = paletteLut[packed & 0x0f];
      pixels[target + 1] = paletteLut[packed >> 4];
      target += 2;
    }
    context.putImageData(imageData, 0, 0);
  }

  function loadCart(bytes: Uint8Array) {
    const pointer = allocate(module, bytes.byteLength);
    try {
      module.HEAPU8.set(bytes, pointer);
      const result = module._f08_load_cart_data(pointer, bytes.byteLength);
      if (result !== 0) {
        throw new Error(
          lastRuntimeError(module) ??
            "The PICO-8 cartridge could not be loaded",
        );
      }
    } finally {
      module._free(pointer);
    }
  }

  function advance(input: Pico8Input) {
    if (disposed) return;
    module._f08_set_inputs(
      input.keyDown,
      input.keyHeld,
      input.mouseX,
      input.mouseY,
      input.mouseButtons,
    );
    module._f08_step_frame();
  }

  function readAudio(target: Int16Array) {
    if (disposed) return 0;
    const written = module._f08_fill_audio_buffer(
      audioPointer,
      Math.min(samplesPerFrame, target.length),
    );
    if (written <= 0) return 0;
    target.set(new Int16Array(module.HEAPU8.buffer, audioPointer, written));
    return written;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    module._free(palettePointer);
    module._free(audioPointer);
  }

  return {
    frameRate: module._f08_get_target_fps() || PICO8_FRAME_RATE,
    audioSampleRate: module._f08_get_audio_sample_rate(),
    samplesPerFrame,
    loadCart,
    advance,
    render,
    readAudio,
    dispose,
  };
}
