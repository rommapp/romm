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

interface Fake08Module {
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
  loadCart: (bytes: Uint8Array) => void;
  step: (input: Pico8Input) => void;
  getAudioSamples: () => Int16Array;
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
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) throw new Error("PICO-8 needs a 2D canvas");
  const renderContext = context;

  canvas.width = PICO8_WIDTH;
  canvas.height = PICO8_HEIGHT;
  renderContext.imageSmoothingEnabled = false;
  module._f08_init();

  const framebufferPointer = module._f08_get_framebuffer_ptr();
  if (!framebufferPointer) throw new Error("PICO-8 framebuffer is unavailable");

  const palettePointer = module._malloc(PALETTE_BYTES);
  const samplesPerFrame = Math.ceil(
    module._f08_get_audio_sample_rate() / PICO8_FRAME_RATE,
  );
  const audioPointer = module._malloc(samplesPerFrame * 2);
  const imageData = renderContext.createImageData(PICO8_WIDTH, PICO8_HEIGHT);
  let disposed = false;

  function render() {
    module._f08_get_palette_rgba(palettePointer);
    const palette = new Uint8Array(
      module.HEAPU8.buffer,
      palettePointer,
      PALETTE_BYTES,
    );
    const framebuffer = new Uint8Array(
      module.HEAPU8.buffer,
      framebufferPointer,
      FRAMEBUFFER_BYTES,
    );

    for (let index = 0; index < FRAMEBUFFER_BYTES; index += 1) {
      const packed = framebuffer[index];
      const firstPixel = index * 2;
      const secondPixel = firstPixel + 1;
      const firstColor = (packed & 0x0f) * 4;
      const secondColor = (packed >> 4) * 4;
      const firstTarget = firstPixel * 4;
      const secondTarget = secondPixel * 4;
      imageData.data[firstTarget] = palette[firstColor];
      imageData.data[firstTarget + 1] = palette[firstColor + 1];
      imageData.data[firstTarget + 2] = palette[firstColor + 2];
      imageData.data[firstTarget + 3] = 255;
      imageData.data[secondTarget] = palette[secondColor];
      imageData.data[secondTarget + 1] = palette[secondColor + 1];
      imageData.data[secondTarget + 2] = palette[secondColor + 2];
      imageData.data[secondTarget + 3] = 255;
    }
    renderContext.putImageData(imageData, 0, 0);
  }

  function loadCart(bytes: Uint8Array) {
    const pointer = module._malloc(bytes.byteLength);
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

  function step(input: Pico8Input) {
    if (disposed) return;
    module._f08_set_inputs(
      input.keyDown,
      input.keyHeld,
      input.mouseX,
      input.mouseY,
      input.mouseButtons,
    );
    module._f08_step_frame();
    render();
  }

  function getAudioSamples() {
    if (disposed) return new Int16Array();
    const written = module._f08_fill_audio_buffer(
      audioPointer,
      samplesPerFrame,
    );
    if (written <= 0) return new Int16Array();
    return new Int16Array(module.HEAPU8.buffer, audioPointer, written).slice();
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
    loadCart,
    step,
    getAudioSamples,
    dispose,
  };
}
