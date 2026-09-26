import { emulatorLabelFrom } from "@/v2/utils/assets";

// Stands in for `@/stores/streaming` via `vi.mock(path, () => import(...))`.
const EMULATOR_LABELS: Record<string, string> = {
  play: "Play!",
  retroarch: "RetroArch",
};

export function useStreamingStore() {
  return {
    emulatorLabel: (id: string | null | undefined) =>
      emulatorLabelFrom(EMULATOR_LABELS, id),
  };
}
