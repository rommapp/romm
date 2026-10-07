import { emulatorLabelFrom } from "@/v2/utils/assets";

// Stands in for `@/stores/streaming` via `vi.mock(path, () => import(...))`.
const EMULATOR_LABELS: Record<string, string> = {
  play: "Play!",
  retroarch: "RetroArch",
};

// The container each platform streams on; tests fill it, empty means no streaming.
export const streamingContainers: Record<string, { emulator: string }> = {};

export function useStreamingStore() {
  return {
    emulatorLabel: (id: string | null | undefined) =>
      emulatorLabelFrom(EMULATOR_LABELS, id),
    containerForPlatform: (slug: string | null | undefined) =>
      (slug && streamingContainers[slug.toLowerCase()]) || null,
  };
}
