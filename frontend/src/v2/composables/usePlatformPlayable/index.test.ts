import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  playTooltip,
  usePlatformPlayable,
  usePlatformPlayableChecker,
} from "./index";

// Controllable stubs. Each test builds a fresh composable after setting these,
// because the values are plain objects and computeds cache.
const ejsSlugs = new Set<string>();
const ruffleSlugs = new Set<string>();
const dosboxSlugs = new Set<string>();
const jsDosSlugs = new Set<string>();
const streamContainers = new Map<string, { label: string; emulator: string }>();
const streamingEnabled = { value: true };

vi.mock("@/utils", () => ({
  isEJSEmulationSupported: (slug: string) => ejsSlugs.has(slug),
  isJsDosEmulationSupported: (slug: string) => jsDosSlugs.has(slug),
  isRuffleEmulationSupported: (slug: string) => ruffleSlugs.has(slug),
  getSupportedEJSCores: (slug: string) =>
    dosboxSlugs.has(slug) ? ["dosbox_pure"] : ["snes9x"],
  resolvePlatformSlug: (slug: string) => slug,
}));
// The composable takes the heartbeat through storeToRefs (so the store's ref
// is literally named `value`) but reads configStore.config directly.
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ value: { value: {} } }),
}));
vi.mock("@/stores/config", () => ({
  default: () => ({ config: { PLATFORMS_VERSIONS: {} } }),
}));
// A Pinia setup store unwraps its refs on the instance, so `config` here is
// the plain object the composable reads, not a ref.
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    config: { enabled: streamingEnabled.value, containers: [] },
    containerForPlatform: (slug: string | null | undefined) =>
      streamingEnabled.value && slug
        ? (streamContainers.get(slug) ?? null)
        : null,
  }),
}));
// storeToRefs would reject the plain objects above; the composable only needs
// the `.value` handle it hands back.
vi.mock("pinia", async (importOriginal) => {
  const actual = await importOriginal<typeof import("pinia")>();
  return { ...actual, storeToRefs: (store: unknown) => store };
});
vi.mock("@/locales", () => ({
  default: {
    global: {
      t: (key: string, params?: Record<string, unknown>) =>
        params ? `${key}:${JSON.stringify(params)}` : key,
    },
  },
}));

beforeEach(() => {
  ejsSlugs.clear();
  ruffleSlugs.clear();
  dosboxSlugs.clear();
  jsDosSlugs.clear();
  streamContainers.clear();
  streamingEnabled.value = true;
});

describe("usePlatformPlayable", () => {
  it("resolves browser-only as browser", () => {
    ejsSlugs.add("snes");
    const { mode, playable } = usePlatformPlayable(() => "snes");
    expect(mode.value).toBe("browser");
    expect(playable.value).toBe(true);
  });

  it("resolves streaming-only as stream and carries the container label", () => {
    streamContainers.set("ps2", { label: "PCSX2", emulator: "pcsx2" });
    const { mode, playable, streamLabel } = usePlatformPlayable(() => "ps2");
    expect(mode.value).toBe("stream");
    expect(playable.value).toBe(false);
    expect(streamLabel.value).toBe("PCSX2");
  });

  it("resolves both when the platform runs in browser and streams", () => {
    ejsSlugs.add("snes");
    streamContainers.set("snes", { label: "RetroArch", emulator: "retroarch" });
    const { mode } = usePlatformPlayable(() => "snes");
    expect(mode.value).toBe("both");
  });

  it("resolves neither as null", () => {
    const { mode } = usePlatformPlayable(() => "xbox");
    expect(mode.value).toBeNull();
  });

  it("falls back to the emulator name when the container has no label", () => {
    streamContainers.set("xbox", { label: "", emulator: "xemu" });
    const { streamLabel } = usePlatformPlayable(() => "xbox");
    expect(streamLabel.value).toBe("xemu");
  });

  it("reports nothing streamable when streaming is disabled", () => {
    streamingEnabled.value = false;
    streamContainers.set("ps2", { label: "PCSX2", emulator: "pcsx2" });
    const { mode, streamLabel } = usePlatformPlayable(() => "ps2");
    expect(streamLabel.value).toBeNull();
    expect(mode.value).toBeNull();
  });
});

describe("usePlatformPlayableChecker", () => {
  it("agrees with the reactive form for the same slug", () => {
    ejsSlugs.add("snes");
    streamContainers.set("ps2", { label: "PCSX2", emulator: "pcsx2" });
    const { isStreamable } = usePlatformPlayableChecker();

    // The sort comparators read the batch form and the tiles read the
    // reactive one, so a slug that disagrees between them shows a badge the
    // grouping contradicts.
    for (const slug of ["ps2", "snes"]) {
      const { mode } = usePlatformPlayable(() => slug);
      expect(isStreamable.value(slug)).toBe(
        mode.value === "stream" || mode.value === "both",
      );
    }
    expect(isStreamable.value("ps2")).toBe(true);
    expect(isStreamable.value("snes")).toBe(false);
  });

  it("reports nothing streamable when streaming is disabled", () => {
    streamingEnabled.value = false;
    streamContainers.set("ps2", { label: "PCSX2", emulator: "pcsx2" });
    const { isStreamable } = usePlatformPlayableChecker();
    expect(isStreamable.value("ps2")).toBe(false);
  });
});

describe("playTooltip", () => {
  it("names the browser engine", () => {
    expect(playTooltip("browser", "ruffle", null)).toBe(
      "platform.playable-browser-ruffle",
    );
    expect(playTooltip("browser", "dosbox", null)).toBe(
      "platform.playable-browser-dosbox",
    );
    expect(playTooltip("browser", "emulatorjs", null)).toBe(
      "platform.playable-browser-emulatorjs",
    );
  });

  it("interpolates the container label for the streaming modes", () => {
    expect(playTooltip("stream", null, "PCSX2")).toBe(
      'platform.playable-stream:{"label":"PCSX2"}',
    );
    expect(playTooltip("both", "emulatorjs", "RetroArch")).toBe(
      'platform.playable-both:{"label":"RetroArch"}',
    );
  });

  it("has a message for a platform with no way to play", () => {
    expect(playTooltip(null, null, null)).toBe("platform.playable-none");
  });
});
