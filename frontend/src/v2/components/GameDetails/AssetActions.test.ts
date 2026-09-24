import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import { saveFixture } from "@/utils/assets.fixtures";
import AssetActions from "./AssetActions.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RBtn = {
  props: { ariaLabel: { type: String, default: "" } },
  emits: ["click"],
  template: `<button class="btn" :aria-label="ariaLabel" @click="$emit('click')" />`,
};

const save = saveFixture({ file_name: "a.srm", is_public: false });

function actions(props: Record<string, unknown> = {}) {
  return mount(AssetActions, {
    props: { asset: save, type: "save", ...props },
    global: { stubs: { RBtn } },
  });
}

describe("AssetActions", () => {
  it("offers only the download for community items", () => {
    const wrapper = actions();

    expect(wrapper.findAll(".btn")).toHaveLength(1);
    expect(wrapper.emitted("download")).toBeUndefined();
    wrapper.get(".btn").trigger("click");
    expect(wrapper.emitted("download")).toHaveLength(1);
  });

  it("adds edit, the heart and delete after the download for own items", async () => {
    const wrapper = actions({ own: true, type: "state" });
    const buttons = wrapper.findAll(".btn");

    expect(buttons.map((b) => b.attributes("aria-label"))).toEqual([
      "rom.download-named",
      "rom.edit-state",
      "rom.add-to-favorites",
      "rom.delete-state",
    ]);

    for (const button of buttons) await button.trigger("click");
    expect(wrapper.emitted("download")).toHaveLength(1);
    expect(wrapper.emitted("edit")).toHaveLength(1);
    expect(wrapper.emitted("toggleFavorite")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
  });

  it("reads the heart off the asset's own state", () => {
    const favorite: SaveSchema = { ...save, is_favorite: true };
    const buttons = actions({ own: true, asset: favorite }).findAll(".btn");

    expect(buttons[2].attributes("aria-label")).toBe(
      "rom.remove-from-favorites",
    );
  });

  it("forwards attributes to its wrapper", () => {
    const wrapper = actions({ "data-row": "x" });

    expect(wrapper.get(".r-asset-actions").attributes("data-row")).toBe("x");
  });
});
