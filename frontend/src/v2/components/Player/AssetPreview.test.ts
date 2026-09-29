import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { stateFixture } from "@/utils/assets.fixtures";
import AssetPreview from "./AssetPreview.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/stores/streaming", () => import("@/test-utils/streamingStore"));

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};

const state = stateFixture({
  file_name: "slot1.state",
  file_size_bytes: 2048,
  emulator: "play",
  updated_at: "2026-05-10T18:45:00Z",
});

describe("AssetPreview", () => {
  it("names the emulator the way the backend labels it", () => {
    const wrapper = mount(AssetPreview, {
      props: { asset: state, type: "state" },
      global: { stubs: { RTag, RIcon: true, RTooltip: true } },
    });

    expect(wrapper.findAll(".tag").map((el) => el.text())).toContain("Play!");
  });
});
