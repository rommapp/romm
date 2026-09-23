import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SaveSchema } from "@/__generated__";
import AssetActions from "./AssetActions.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RBtn = {
  props: { ariaLabel: { type: String, default: "" } },
  emits: ["click"],
  template: `<button class="btn" :aria-label="ariaLabel" @click="$emit('click')" />`,
};

const save = { file_name: "a.srm", is_public: false } as SaveSchema;

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

  it("adds the heart, label, visibility toggle and delete for own items", async () => {
    const wrapper = actions({ own: true, type: "state" });
    const buttons = wrapper.findAll(".btn");

    expect(buttons).toHaveLength(5);
    expect(buttons[0].attributes("aria-label")).toBe("rom.add-to-favorites");
    expect(buttons[1].attributes("aria-label")).toBe("rom.add-labels");
    expect(buttons[2].attributes("aria-label")).toBe("rom.make-public");
    expect(buttons[4].attributes("aria-label")).toBe("rom.delete-state");

    await buttons[0].trigger("click");
    await buttons[1].trigger("click");
    await buttons[2].trigger("click");
    await buttons[4].trigger("click");
    expect(wrapper.emitted("toggleFavorite")).toHaveLength(1);
    expect(wrapper.emitted("editLabels")).toHaveLength(1);
    expect(wrapper.emitted("toggleVisibility")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
  });

  it("reads the heart and labels buttons off the asset's own state", () => {
    const labelled = {
      ...save,
      is_favorite: true,
      labels: ["100% run", "no deaths"],
    } as SaveSchema;
    const buttons = actions({ own: true, asset: labelled }).findAll(".btn");

    expect(buttons[0].attributes("aria-label")).toBe(
      "rom.remove-from-favorites",
    );
    expect(buttons[1].attributes("aria-label")).toBe("rom.edit-labels");
  });

  it("forwards attributes to its wrapper", () => {
    const wrapper = actions({ "data-row": "x" });

    expect(wrapper.get(".r-asset-actions").attributes("data-row")).toBe("x");
  });
});
