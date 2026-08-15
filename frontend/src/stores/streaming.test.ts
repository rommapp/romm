import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useStreamingStore } from "@/stores/streaming";

describe("platformCapabilities disc flags", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("maps the backend disc flags to camelCase", () => {
    const store = useStreamingStore();
    store.config = {
      enabled: true,
      containers: [
        {
          platform: "dc",
          host: "http://x",
          label: "RetroArch",
          emulator: "retroarch",
          capabilities: {
            max_slots: 0,
            has_autosave: true,
            autosave_slot: 10,
            supports_disc_swap: true,
            has_manual_disc_swap: false,
          },
        },
      ],
    };
    expect(store.platformCapabilities("dc").supportsDiscSwap).toBe(true);
    expect(store.platformCapabilities("dc").hasManualDiscSwap).toBe(false);
  });

  it("reports no disc swap for an unconfigured platform", () => {
    const store = useStreamingStore();
    expect(store.platformCapabilities("dc").supportsDiscSwap).toBe(false);
  });
});
