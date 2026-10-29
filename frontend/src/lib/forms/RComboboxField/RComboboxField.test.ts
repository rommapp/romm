import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/lib/overlays/RDialog/escapeStack";
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

  afterEach(() => {
    popEscapable(dialog);
  });

  function pressEscape(el: Element): KeyboardEvent {
    const event = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    el.dispatchEvent(event);
    return event;
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

  it("leaves Escape unclaimed on a page when it has nothing to show", async () => {
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], items: ["rpg"] },
      attachTo: document.body,
    });
    const input = wrapper.get("input");

    await input.setValue("zzz");

    expect(pressEscape(input.element).defaultPrevented).toBe(false);
    wrapper.unmount();
  });

  it("stays open for a press inside an overlay opened above it", async () => {
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], items: ["rpg", "racing"] },
      attachTo: document.body,
    });
    await wrapper.get("input").trigger("focus");
    expect(document.querySelector(".r-combobox-field__panel")).not.toBeNull();

    const nested = document.createElement("div");
    document.body.append(nested);
    const menu: EscapableEntry = {
      close: vi.fn(),
      persistent: false,
      panel: () => nested,
    };
    pushEscapable(menu);

    nested.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
    await nextTick();
    expect(document.querySelector(".r-combobox-field__panel")).not.toBeNull();

    popEscapable(menu);
    nested.remove();
    document.body.dispatchEvent(
      new PointerEvent("pointerdown", { bubbles: true }),
    );
    await nextTick();
    expect(document.querySelector(".r-combobox-field__panel")).toBeNull();
    wrapper.unmount();
  });
});

describe("RComboboxField commas", () => {
  async function type(allowCommas: boolean, text: string) {
    const wrapper = mount(RComboboxField, {
      props: { modelValue: [], allowCommas },
    });
    const input = wrapper.get("input");
    await input.setValue(text);
    await input.trigger("keydown", { key: "Enter" });
    return wrapper.emitted("update:modelValue")?.[0]?.[0];
  }

  it("splits a typed value on commas by default", async () => {
    expect(await type(false, "Hey You, Pikachu!")).toEqual([
      "Hey You",
      "Pikachu!",
    ]);
  });

  it("keeps the commas of a value when allowed", async () => {
    expect(await type(true, "Hey You, Pikachu!")).toEqual([
      "Hey You, Pikachu!",
    ]);
  });
});

describe("RComboboxField combobox semantics", () => {
  function mountField(props: Record<string, unknown> = {}) {
    return mount(RComboboxField, {
      props: {
        items: ["Action", "Adventure", "Puzzle"],
        label: "Genres",
        ...props,
      },
      attachTo: document.body,
    });
  }

  it("marks the input as a closed combobox that controls nothing yet", () => {
    const wrapper = mountField();
    const input = wrapper.get("input");

    expect(input.attributes("role")).toBe("combobox");
    expect(input.attributes("aria-autocomplete")).toBe("list");
    expect(input.attributes("aria-expanded")).toBe("false");
    expect(input.attributes("aria-controls")).toBeUndefined();
    expect(input.attributes("aria-activedescendant")).toBeUndefined();
    wrapper.unmount();
  });

  it("points at the named listbox and the active suggestion while open", async () => {
    const wrapper = mountField();
    const input = wrapper.get("input");

    await input.trigger("focus");
    expect(input.attributes("aria-expanded")).toBe("true");
    const listbox = document.getElementById(input.attributes("aria-controls")!);
    expect(listbox?.getAttribute("role")).toBe("listbox");
    expect(listbox?.getAttribute("aria-label")).toBe("Genres");
    expect(input.attributes("aria-activedescendant")).toBeUndefined();

    await input.trigger("keydown", { key: "ArrowDown" });
    await input.trigger("keydown", { key: "ArrowDown" });
    const active = document.getElementById(
      input.attributes("aria-activedescendant")!,
    );
    expect(active?.textContent?.trim()).toBe("Adventure");
    expect(active?.getAttribute("role")).toBe("option");
    expect(active?.parentElement).toBe(listbox);
    wrapper.unmount();
  });

  it("drops the pointers once the panel closes", async () => {
    const wrapper = mountField();
    const input = wrapper.get("input");
    await input.trigger("focus");
    await input.trigger("keydown", { key: "ArrowDown" });

    await input.trigger("keydown", { key: "Escape" });
    await nextTick();

    expect(input.attributes("aria-expanded")).toBe("false");
    expect(input.attributes("aria-controls")).toBeUndefined();
    expect(input.attributes("aria-activedescendant")).toBeUndefined();
    wrapper.unmount();
  });

  it("stays a plain text field without suggestions", () => {
    const wrapper = mountField({ noSuggestions: true });
    const input = wrapper.get("input");

    expect(input.attributes("role")).toBeUndefined();
    expect(input.attributes("aria-expanded")).toBeUndefined();
    wrapper.unmount();
  });
});
