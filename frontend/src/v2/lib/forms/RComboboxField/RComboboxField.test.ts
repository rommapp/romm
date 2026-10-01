import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
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

describe("RComboboxField inside an overlay", () => {
  const dialog: EscapableEntry = { close: vi.fn(), persistent: false };

  afterEach(() => popEscapable(dialog));

  function pressEscape(el: Element) {
    el.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
  }

  it("closes its suggestions on Escape, leaving the dialog open", async () => {
    pushEscapable(dialog);
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], items: ["rpg", "racing"] },
      attachTo: document.body,
    });
    const input = wrapper.get("input");

    await input.trigger("focus");
    expect(document.querySelector(".r-combobox-field__panel")).not.toBeNull();

    pressEscape(input.element);
    await nextTick();

    expect(document.querySelector(".r-combobox-field__panel")).toBeNull();
    expect(dialog.close).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("does not hold Escape back when it has nothing to show", async () => {
    pushEscapable(dialog);
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], items: [] },
      attachTo: document.body,
    });
    const input = wrapper.get("input");

    await input.trigger("focus");
    pressEscape(input.element);

    expect(dialog.close).toHaveBeenCalledOnce();
    wrapper.unmount();
  });
});
