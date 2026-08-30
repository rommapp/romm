import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { SimpleRom } from "@/stores/roms";
import { useCanPlay } from "./index";

// Each engine's support check is stubbed so a test can enable one route at a
// time and assert the gating around it, not the platform tables themselves.
const support = vi.hoisted(() => ({
  ejs: vi.fn(() => false),
  jsDos: vi.fn(() => false),
  ruffle: vi.fn(() => false),
  // js-dos also demands its own bundle format; on by default so the engine
  // stubs stay the only variable.
  jsDosBundle: vi.fn(() => true),
}));

const heartbeat = ref({});
// The streaming route is a store lookup rather than an engine check: a
// container configured for the platform makes the rom streamable.
const streamContainer = ref<object | null>(null);

vi.mock("pinia", () => ({
  storeToRefs: () => ({ value: heartbeat }),
}));
vi.mock("@/stores/config", () => ({ default: () => ({ config: {} }) }));
vi.mock("@/stores/heartbeat", () => ({ default: () => ({}) }));
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    containerForPlatform: () => streamContainer.value,
  }),
}));
vi.mock("@/utils", () => ({
  isEJSEmulationSupported: support.ejs,
  isJsDosEmulationSupported: support.jsDos,
  isRuffleEmulationSupported: support.ruffle,
  isJsDosBundle: support.jsDosBundle,
}));

function makeRom(overrides: Partial<SimpleRom> = {}): SimpleRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    platform_slug: "snes",
    has_file_on_disk: true,
    ...overrides,
  } as unknown as SimpleRom;
}

beforeEach(() => {
  support.ejs.mockReturnValue(false);
  support.jsDos.mockReturnValue(false);
  support.ruffle.mockReturnValue(false);
  support.jsDosBundle.mockReturnValue(true);
  support.ejs.mockClear();
  support.jsDos.mockClear();
  support.ruffle.mockClear();
  support.jsDosBundle.mockClear();
  streamContainer.value = null;
});

describe("useCanPlay", () => {
  it.each([
    ["EJS", "ejs", "canPlayEJS"],
    ["js-dos", "jsDos", "canPlayJsDos"],
    ["Ruffle", "ruffle", "canPlayRuffle"],
  ] as const)("reports %s support on its own flag", (_label, stub, flag) => {
    support[stub].mockReturnValue(true);
    const result = useCanPlay(() => makeRom());

    expect(result[flag].value).toBe(true);
    expect(result.canPlay.value).toBe(true);
  });

  // A physical game, or one whose file vanished from the library, has nothing
  // to hand the emulator: every route boots from the download endpoint.
  it.each(["ejs", "jsDos", "ruffle"] as const)(
    "refuses %s for a rom with no file on disk",
    (stub) => {
      support[stub].mockReturnValue(true);
      const { canPlay } = useCanPlay(() =>
        makeRom({ has_file_on_disk: false }),
      );

      expect(canPlay.value).toBe(false);
      expect(support[stub]).not.toHaveBeenCalled();
    },
  );

  it("refuses every route when there is no rom", () => {
    support.ejs.mockReturnValue(true);
    support.jsDos.mockReturnValue(true);
    support.ruffle.mockReturnValue(true);
    streamContainer.value = {};
    const { canPlay, canPlayEJS, canPlayJsDos, canPlayRuffle, canPlayStream } =
      useCanPlay(() => null);

    expect(canPlay.value).toBe(false);
    expect(canPlayEJS.value).toBe(false);
    expect(canPlayJsDos.value).toBe(false);
    expect(canPlayRuffle.value).toBe(false);
    expect(canPlayStream.value).toBe(false);
  });

  // Streaming runs the platform's real emulator in a container, so it makes a
  // rom playable on its own even where no in-browser engine can touch it.
  it("reports streaming support on its own flag", () => {
    streamContainer.value = {};
    const { canPlay, canPlayStream } = useCanPlay(() => makeRom());

    expect(canPlayStream.value).toBe(true);
    expect(canPlay.value).toBe(true);
  });

  // The broker is handed the ROM file, so streaming needs one just as the
  // in-browser engines do.
  it("refuses streaming for a rom with no file on disk", () => {
    streamContainer.value = {};
    const { canPlay, canPlayStream } = useCanPlay(() =>
      makeRom({ has_file_on_disk: false }),
    );

    expect(canPlayStream.value).toBe(false);
    expect(canPlay.value).toBe(false);
  });

  // A bare game folder or plain archive makes js-dos panic with
  // "Broken bundle", so offering Play would hand the user a dead player.
  it("refuses js-dos for a rom that is not a bundle", () => {
    support.jsDos.mockReturnValue(true);
    support.jsDosBundle.mockReturnValue(false);
    const { canPlay, canPlayJsDos } = useCanPlay(() => makeRom());

    expect(canPlayJsDos.value).toBe(false);
    expect(canPlay.value).toBe(false);
  });

  it("stays unplayable when no engine supports the platform", () => {
    const { canPlay } = useCanPlay(() => makeRom());

    expect(canPlay.value).toBe(false);
  });

  it("re-evaluates when the rom behind the getter changes", () => {
    support.jsDos.mockReturnValue(true);
    const rom = ref(makeRom({ has_file_on_disk: false }));
    const { canPlay } = useCanPlay(() => rom.value);

    expect(canPlay.value).toBe(false);

    rom.value = makeRom();
    expect(canPlay.value).toBe(true);
  });
});
