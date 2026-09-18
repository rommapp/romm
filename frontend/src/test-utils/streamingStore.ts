// Stands in for `@/stores/streaming` via `vi.mock(path, () => import(...))`.
const EMULATOR_LABELS: Record<string, string> = {
  play: "Play!",
  retroarch: "RetroArch",
};

export function useStreamingStore() {
  return {
    emulatorLabel: (id: string) => EMULATOR_LABELS[id.toLowerCase()] ?? id,
  };
}
