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

  it("adds the visibility toggle and delete for own items", async () => {
    const wrapper = actions({ own: true, type: "state" });
    const buttons = wrapper.findAll(".btn");

    expect(buttons).toHaveLength(3);
    expect(buttons[0].attributes("aria-label")).toBe("rom.make-public");
    expect(buttons[2].attributes("aria-label")).toBe("rom.delete-state");

    await buttons[0].trigger("click");
    await buttons[2].trigger("click");
    expect(wrapper.emitted("toggleVisibility")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
  });

  it("forwards attributes to its wrapper", () => {
    const wrapper = actions({ "data-row": "x" });

    expect(wrapper.get(".r-asset-actions").attributes("data-row")).toBe("x");
  });
});
