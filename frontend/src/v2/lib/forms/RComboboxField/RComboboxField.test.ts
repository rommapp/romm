import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import RComboboxField from "./RComboboxField.vue";

describe("RComboboxField rules", () => {
  const atLeastOne = (v: string[]) => v.length > 0 || "Add a tag";

  it("stays quiet until validated, then tracks the chips", async () => {
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], rules: [atLeastOne] },
    });
    const error = () => wrapper.find(".r-combobox-field__details--error");
    expect(error().exists()).toBe(false);

    expect(wrapper.vm.validate()).toBe(false);
    await nextTick();
    expect(error().text()).toBe("Add a tag");

    await wrapper.setProps({ modelValue: ["rpg"] });
    expect(error().exists()).toBe(false);
    wrapper.unmount();
  });

  it("re-checks a touched field when its rules change", async () => {
    const wrapper = mount(RComboboxField, {
      props: { modelValue: ["rpg"], rules: [] },
    });
    wrapper.vm.validate();

    await wrapper.setProps({ rules: [() => "Too many tags"] });
    expect(wrapper.get(".r-combobox-field__details--error").text()).toBe(
      "Too many tags",
    );
    wrapper.unmount();
  });
});
