import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import AssetPreview from "./AssetPreview.vue";

vi.mock("vue-i18n", async () => {
  const { ref } = await import("vue");
  return { useI18n: () => ({ t: (key: string) => key, locale: ref("en-US") }) };
});
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    emulatorLabel: (id: string) => (id === "play" ? "Play!" : id),
  }),
}));

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};

const save = {
  file_name: "slot1.ps2",
  file_size_bytes: 2048,
  emulator: "play",
  updated_at: "2026-05-10T18:45:00Z",
} as SaveSchema;

describe("AssetPreview", () => {
  it("names the emulator the way the backend labels it", () => {
    const wrapper = mount(AssetPreview, {
      props: { asset: save, type: "save" },
      global: { stubs: { RTag, RIcon: true, RTooltip: true } },
    });

    expect(wrapper.findAll(".tag").map((el) => el.text())).toContain("Play!");
  });
});
