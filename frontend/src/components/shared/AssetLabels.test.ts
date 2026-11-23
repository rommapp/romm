import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { SaveSchema } from "@/__generated__";
import { saveFixture } from "@/utils/assets.fixtures";
import AssetLabels from "./AssetLabels.vue";

const RTag = {
  props: { text: { type: String, default: "" } },
  template: `<span class="tag">{{ text }}</span>`,
};

const save = saveFixture({ file_size_bytes: 2048, emulator: "snes9x" });

function labels(asset: SaveSchema) {
  return mount(AssetLabels, { props: { asset }, global: { stubs: { RTag } } });
}

describe("AssetLabels", () => {
  it("renders one chip per label, in order", () => {
    const wrapper = labels({ ...save, labels: ["100% run", "no deaths"] });

    expect(wrapper.findAll(".tag").map((el) => el.text())).toEqual([
      "100% run",
      "no deaths",
    ]);
  });

  it("renders nothing when the asset carries no labels", () => {
    expect(labels(save).find(".r-asset-labels").exists()).toBe(false);
  });
});
