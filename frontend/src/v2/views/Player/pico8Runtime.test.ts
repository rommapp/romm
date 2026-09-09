import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPico8Runtime, type Fake08Module } from "./pico8Runtime";

const heap = new Uint8Array(new ArrayBuffer(64 * 1024));
const context = {
  createImageData: vi.fn((width: number, height: number): ImageData => ({
    data: new Uint8ClampedArray(width * height * 4),
    width,
    height,
    colorSpace: "srgb",
  })),
  putImageData: vi.fn(),
};

// Hand out distinct addresses so the palette and audio buffers do not alias.
let nextAddress = 200;
const fakeModule = {
  HEAPU8: heap,
  _f08_init: vi.fn(),
  _f08_load_cart_data: vi.fn(() => 0),
  _f08_step_frame: vi.fn(),
  _f08_get_framebuffer_ptr: vi.fn(() => 100),
  _f08_get_palette_rgba: vi.fn((pointer: number) => {
    heap[pointer + 4] = 1;
    heap[pointer + 5] = 2;
    heap[pointer + 6] = 3;
    heap[pointer + 8] = 4;
    heap[pointer + 9] = 5;
    heap[pointer + 10] = 6;
  }),
  _f08_get_target_fps: vi.fn(() => 30),
  _f08_get_last_error: vi.fn(() => 0),
  _f08_set_inputs: vi.fn(),
  _f08_fill_audio_buffer: vi.fn((pointer: number) => {
    new Int16Array(heap.buffer, pointer, 2).set([1000, -1000]);
    return 2;
  }),
  _f08_get_audio_sample_rate: vi.fn(() => 22050),
  _malloc: vi.fn((size: number) => {
    const address = nextAddress;
    nextAddress += size;
    return address;
  }),
  _free: vi.fn(),
  UTF8ToString: vi.fn(() => ""),
} satisfies Fake08Module;

vi.mock("./scriptLoader", () => ({
  loadScript: vi.fn(async () => {
    window.Fake08Module = vi.fn(async () => fakeModule);
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  nextAddress = 200;
  heap[100] = 0x21;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
});

describe("createPico8Runtime", () => {
  it("loads cartridges, maps frames to pixels, and exposes audio", async () => {
    const runtime = await createPico8Runtime(document.createElement("canvas"));

    runtime.loadCart(new Uint8Array([1, 2, 3]));
    runtime.advance({
      keyDown: 0x10,
      keyHeld: 0x30,
      mouseX: 12,
      mouseY: 34,
      mouseButtons: 1,
    });
    runtime.render();

    expect(fakeModule._f08_load_cart_data).toHaveBeenCalledWith(
      expect.any(Number),
      3,
    );
    expect(fakeModule._f08_set_inputs).toHaveBeenCalledWith(
      0x10,
      0x30,
      12,
      34,
      1,
    );
    expect(context.putImageData).toHaveBeenCalled();
    const image = context.putImageData.mock.calls[0][0] as ImageData;
    expect([...image.data.slice(0, 8)]).toEqual([1, 2, 3, 255, 4, 5, 6, 255]);
    expect([...runtime.getAudioSamples()]).toEqual([1000, -1000]);
    expect(runtime.frameRate).toBe(30);
    expect(runtime.audioSampleRate).toBe(22050);

    runtime.dispose();
    runtime.advance({
      keyDown: 0,
      keyHeld: 0,
      mouseX: 0,
      mouseY: 0,
      mouseButtons: 0,
    });
    expect(fakeModule._f08_step_frame).toHaveBeenCalledTimes(1);
  });
});
