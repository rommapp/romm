// Stands in for `@/stores/streaming` via `vi.mock(path, () => import(...))`.
const EMULATOR_LABELS: Record<string, string> = {
  play: "Play!",
  retroarch: "RetroArch",
};

export function useStreamingStore() {
  return {
    emulatorLabel: (id: string | null | undefined) => {
      if (!id) return "";
      const key = id.toLowerCase();
      return Object.hasOwn(EMULATOR_LABELS, key) ? EMULATOR_LABELS[key] : id;
    },
  };
}
